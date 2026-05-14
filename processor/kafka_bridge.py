import json
import os
import paho.mqtt.client as mqtt
from confluent_kafka import SerializingProducer
from confluent_kafka.serialization import StringSerializer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

# Config
MQTT_BROKER = os.getenv('MQTT_BROKER', 'mosquitto')
MQTT_USER = os.getenv('MQTT_USER', 'bridge')
MQTT_PASS = os.getenv('MQTT_PASS', 'bridge_pass')
KAFKA_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')

schema_str = """
{
  "namespace": "factory.telemetry",
  "type": "record",
  "name": "TelemetryRecord",
  "fields": [
    {"name": "machine_id", "type": "string"},
    {"name": "timestamp", "type": "double"},
    {"name": "temperature", "type": "double"},
    {"name": "rpm", "type": "double"},
    {"name": "vibration", "type": "double"},
    {"name": "current", "type": "double"},
    {"name": "status", "type": "string"}
  ]
}
"""

SCHEMA_REGISTRY_URL = os.getenv('SCHEMA_REGISTRY_URL', 'http://schema-registry:8081')
schema_registry_conf = {'url': SCHEMA_REGISTRY_URL}
schema_registry_client = SchemaRegistryClient(schema_registry_conf)

avro_serializer = AvroSerializer(schema_registry_client, schema_str)
string_serializer = StringSerializer('utf_8')

# Kafka Producer Config
kafka_conf = {
    'bootstrap.servers': KAFKA_SERVERS,
    'key.serializer': string_serializer,
    'value.serializer': avro_serializer,
    'client.id': 'mqtt-kafka-bridge'
}
producer = SerializingProducer(kafka_conf)

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode())
        machine_id = data.get('machine_id', 'unknown')
        
        # Ensure all required fields for Avro
        avro_data = {
            "machine_id": str(machine_id),
            "timestamp": float(data.get('timestamp', 0.0)),
            "temperature": float(data.get('temperature', 0.0)),
            "rpm": float(data.get('rpm', 0.0)),
            "vibration": float(data.get('vibration', 0.0)),
            "current": float(data.get('current', 0.0)),
            "status": str(data.get('status', 'UNKNOWN'))
        }

        # Industrial Req: Partitioning by machine_id
        # This ensures all messages from the same machine go to the same partition
        # and maintain strict chronological order.
        producer.produce(
            topic='factory_telemetry',
            key=machine_id,
            value=avro_data,
            on_delivery=delivery_report
        )
        producer.poll(0)
        print(f"Bridged MQTT -> Kafka: {machine_id}")
    except Exception as e:
        print(f"Bridge Error: {e}")

# MQTT Setup
mqtt_client = mqtt.Client("KafkaBridge")
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER)
mqtt_client.subscribe("factory/#", qos=1)

print("MQTT-Kafka Bridge started...")
mqtt_client.loop_forever()
