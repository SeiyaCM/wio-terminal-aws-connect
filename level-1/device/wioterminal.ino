#include <AWS_IOT.h>
#include <rpcWiFi.h>
#include <ArduinoJson.h>
#include "SPI.h"
#include "secrets.h"

AWS_IOT hornbill;

static auto constexpr TOPIC_NAME = "topic/device/data";

int msgReceived = 0;
char reportpayload[512];
char rcvdPayload[512];
char desiredPayload[512];

// 測定周期 
int period = 5000;

void publishMessage()
{
  StaticJsonDocument<200> doc;

  // ランダムな値を生成
  // humidity: 40.0 ~ 80.0
  float humidity = random(400, 801) / 10.0;
  // temperature: 15.0 ~ 35.0
  float temperature = random(150, 351) / 10.0;

  doc["humidity"] = humidity;
  doc["temperature"] = temperature;
  doc["deviceID"] = "00001";
  char jsonBuffer[512];
  serializeJson(doc, jsonBuffer);

  if(hornbill.publish(TOPIC_NAME, jsonBuffer) == 0)
  {        
    Serial.print("Publish Message:");
    Serial.println(jsonBuffer);
  }
  else {
    Serial.println("Publish Failed");
  }
}

void setup() {
  Serial.println(period);
  Serial.begin(9600);

  // ランダム関数の初期化
  randomSeed(analogRead(0));

  // WiFiに接続
  delay(2000);
  Serial.print("Attempting to connect WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while(WiFi.status() != WL_CONNECTED)
  {
    delay(1000);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("Success Connect to WiFi!!");

  //AWSに接続
  Serial.print("Attempting to connect AWS");
  while(hornbill.connect(AWS_IOT_ENDPOINT, CLIENT_ID, AWS_CERT_CA, AWS_CERT_CRT, AWS_CERT_PRIVATE) != 0)
  {
    Serial.print(".");
    delay(1000);
  }
  Serial.println("");
  Serial.println("Success Connect to AWS!!");
  delay(2000);
}

void loop() {
  publishMessage();
  delay(period);
}
