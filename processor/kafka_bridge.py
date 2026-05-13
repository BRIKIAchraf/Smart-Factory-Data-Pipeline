import json
import os
import paho.mqtt.client as mqtt
from confluent_kafka import Producer

# Config
MQTT_BROKER = os.getenv('MQTT_BROKER', 'mosquitto')
KAFKA_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')

# Kafka Producer Config
kafka_conf = {
    'bootstrap.servers': KAFKA_SERVERS,
    'client.id': 'mqtt-kafka-bridge'
}
producer = Producer(kafka_conf)

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode())
        machine_id = data.get('machine_id', 'unknown')
        
        # Industrial Req: Partitioning by machine_id
        # This ensures all messages from the same machine go to the same partition
        # and maintain strict chronological order.
        producer.produce(
            topic='factory_telemetry',
            key=machine_id,
            value=message.payload,
            callback=delivery_report
        )
        producer.flush()
        print(f"Bridged MQTT -> Kafka: {machine_id}")
    except Exception as e:
        print(f"Bridge Error: {e}")

# MQTT Setup
mqtt_client = mqtt.Client("KafkaBridge")
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER)
mqtt_client.subscribe("factory/#", qos=1)

print("MQTT-Kafka Bridge started...")
mqtt_client.loop_forever()
