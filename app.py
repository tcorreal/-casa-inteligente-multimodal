#include <ArduinoJson.h>    // Para parsear JSON
#include <WiFi.h>           // WiFi ESP32
#include <PubSubClient.h>   // MQTT
#include <ESP32Servo.h>     // Servo ESP32

StaticJsonDocument<200> doc;
StaticJsonDocument<200> doc2;

const char* ssid = "Wokwi-GUEST";      // WiFi de Wokwi
const char* password = "";             // Sin contraseña
const char* mqtt_server = "broker.hivemq.com"; // Mismo broker que usarás en Streamlit

WiFiClient espClient;
PubSubClient client(espClient);

Servo myservo;

String sr2 = "";
String inputString = "";
char rec[50];

void setup() {
  pinMode(2, OUTPUT);          // LED en GPIO2 = Luz de la sala

  myservo.setPeriodHertz(50);  // Servo estándar 50 Hz
  myservo.attach(13, 500, 2400); // Servo en GPIO13 (puerta)

  Serial.begin(115200);
  setup_wifi();

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Conectando a ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi conectada");
  Serial.println("Direccion IP: ");
  Serial.println(WiFi.localIP());
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Esperando conexion MQTT...");
    if (client.connect("ESP32_Casa_Inteligente")) {
      Serial.println("conectado");
      // Nos suscribimos al topic que usa Streamlit
      client.subscribe("cmqtt_a");
    } else {
      Serial.print("falla, rc=");
      Serial.print(client.state());
      Serial.println("  Intento de nuevo en 5 segundos");
      delay(5000);
    }
  }
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}

// callback: se ejecuta cuando llega un mensaje MQTT
void callback(char* topic, byte* payload, unsigned int length) {

  Serial.print("Mensaje recibido en topic: ");
  Serial.println(topic);

  sr2 = "";
  for (int i = 0; i < length; i++) {
    rec[i] = payload[i];
    sr2 += (char)payload[i];
  }
  rec[length] = '\0';

  inputString = sr2;
  Serial.print("Payload: ");
  Serial.println(inputString);

  char msg2[inputString.length() + 1];
  inputString.toCharArray(msg2, inputString.length() + 1);

  StaticJsonDocument<200> doc2;
  DeserializationError error = deserializeJson(doc2, msg2);

  if (error) {
    Serial.print(F("deserializeJson() failed: "));
    Serial.println(error.f_str());
    return;
  }

  // MAPEOS PARA ESTE PROYECTO:
  // Act1   -> Luz sala (ON/OFF)
  // Analog -> Puerta (0-100) -> 0-180 grados

  String value = doc2["Act1"];      // "ON" o "OFF"
  float value_servo = doc2["Analog"]; // 0-100

  // Luz sala en GPIO2
  if (value == "OFF") {
    digitalWrite(2, LOW);
  }
  if (value == "ON") {
    digitalWrite(2, HIGH);
  }

  // Puerta: valor 0-100 -> ángulo 0-180 grados
  if (value_servo >= 0) {
    int val = map(value_servo, 0, 100, 0, 180);
    myservo.write(val);
  }
}
