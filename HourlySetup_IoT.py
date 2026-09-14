import time, json
import board, busio
import adafruit_ahtx0
import RPi.GPIO as GPIO
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

# --- GPIO setup ---
PIR_PIN = 23     # GPIO23 = physical pin 16

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# --- I2C + Sensor setup ---
i2c = busio.I2C(board.SCL, board.SDA)
aht = adafruit_ahtx0.AHTx0(i2c)

# --- AWS IoT settings ---
ENDPOINT  = "a2tbu5f0vot3rq-ats.iot.us-east-2.amazonaws.com"
CLIENT_ID = "Pi-Themostat-v1"
CERT = 
PRIV = 
ROOT = 
TOPIC_TELE = f"smartthermo/{CLIENT_ID}/telemetry"

# --- Configuration for hourly operation ---
SENSOR_WARMUP_TIME = 60   # seconds to let sensor stabilize
MOTION_SAMPLE_TIME = 10   # seconds to sample motion sensor
MQTT_TIMEOUT = 10         # seconds to wait for MQTT operations

def connect_mqtt():
    """Establish MQTT connection to AWS IoT Core"""
    elg = io.EventLoopGroup(1)
    r = io.DefaultHostResolver(elg)
    b = io.ClientBootstrap(elg, r)
    conn = mqtt_connection_builder.mtls_from_path(
        endpoint=ENDPOINT,
        cert_filepath=CERT,
        pri_key_filepath=PRIV,
        ca_filepath=ROOT,
        client_bootstrap=b,
        client_id=CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30
    )
    print("Connecting to AWS IoT...")
    conn.connect().result(timeout=MQTT_TIMEOUT)
    print("Connected to AWS IoT Core.")
    return conn

def publish_telemetry(conn, temp_f, humidity, motion):
    """Publish sensor data to AWS IoT"""
    payload = {
        "ts": int(time.time()),
        "device": CLIENT_ID,
        "motion": bool(motion),
        "temperature_f": round(temp_f, 2),
        "humidity_pct": round(humidity, 2)
    }
    conn.publish(
        topic=TOPIC_TELE, 
        payload=json.dumps(payload), 
        qos=mqtt.QoS.AT_LEAST_ONCE
    ).result(timeout=MQTT_TIMEOUT)
    print(f"[TX] {TOPIC_TELE}: {payload}")

def sample_motion(duration):
    """Sample PIR sensor for specified duration, return True if motion detected"""
    print(f"Sampling motion for {duration} seconds...")
    motion_detected = False
    end_time = time.time() + duration
    
    while time.time() < end_time:
        if GPIO.input(PIR_PIN) == 1:
            motion_detected = True
            print("Motion detected during sampling period!")
        time.sleep(0.1)  # Poll at 10Hz
    
    return motion_detected

def main():
    """Main execution - runs once per power cycle"""
    print("="*50)
    print("Smart Thermostat - Hourly Power Cycle Mode")
    print("="*50)
    
    try:
        # Step 1: Sensor warm-up
        print(f"Warming up sensors for {SENSOR_WARMUP_TIME} seconds...")
        time.sleep(SENSOR_WARMUP_TIME)
        
        # Step 2: Read temperature and humidity
        print("Reading temperature and humidity...")
        temperature_c = aht.temperature
        humidity = aht.relative_humidity
        temperature_f = (temperature_c * 9 / 5) + 32
        print(f"Temp: {temperature_f:.2f} F   Humidity: {humidity:.2f} %")
        
        # Step 3: Sample motion
        motion_detected = sample_motion(MOTION_SAMPLE_TIME)
        
        # Step 4: Connect to AWS IoT
        mqtt_conn = connect_mqtt()
        
        # Step 5: Publish telemetry
        print("Publishing telemetry data...")
        publish_telemetry(mqtt_conn, temperature_f, humidity, motion_detected)
        
        # Step 6: Disconnect gracefully
        print("Disconnecting from AWS IoT...")
        mqtt_conn.disconnect().result(timeout=MQTT_TIMEOUT)
        print("Disconnected successfully.")
        
        print("="*50)
        print("Data transmission complete. System will power down.")
        print("="*50)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        GPIO.cleanup()
        print("GPIO cleanup complete. Ready for power-off.")

if __name__ == "__main__":
    main()
