#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- 1. Identifiants Wi-Fi ---
const char* ssid = "Wifi_Iot215";
const char* password = "CIEL1234#+";

// --- 2. Adresse de l'API (serveur Raspberry Pi de L.B.) ---
const char* API_URL = "http://172.16.10.239:5000/api/pir/event";
const char* SENSOR_ID = "esp32_pir_01";

// --- 3. Broches du matériel ---
const int PIR_PIN = 27; // Signal du capteur PIR
const int LED_PIN = 23; // LED rouge (simule l'éclairage salle 215)

// --- 4. Temporisation ---
// 5000 = 5 secondes pour les tests | 120000 = 2 minutes pour le vrai système
const unsigned long DELAI_ECLAIRAGE = 5000;
unsigned long chronometre = 0;      // Dernier mouvement détecté
unsigned long debutMouvement = 0;   // Début de la période d'occupation
bool lumiereAllumee = false;

// --- 5. Envoi vers l'API ---
// status : "active" (mouvement) ou "inactive" (plus de mouvement)
// duration : durée en secondes
void envoyerEvenementAPI(const char* status, unsigned long duration) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Erreur : Wi-Fi déconnecté, tentative de reconnexion...");
    WiFi.reconnect();
    return;
  }

  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  // JSON au format attendu par l'API
  JsonDocument doc;
  doc["sensor_id"] = SENSOR_ID;
  doc["duration"] = duration;
  doc["status"] = status;

  String requestBody;
  serializeJson(doc, requestBody);
  Serial.println("--> Envoi à l'API : " + requestBody);

  int httpResponseCode = http.POST(requestBody);

  if (httpResponseCode > 0) {
    Serial.print("    Code HTTP : ");
    Serial.println(httpResponseCode); // Attendu : 201
    Serial.println("    Réponse : " + http.getString());
  } else {
    Serial.print("    Erreur réseau : ");
    Serial.println(http.errorToString(httpResponseCode));
  }
  http.end();
}

void setup() {
  Serial.begin(115200);

  pinMode(PIR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH); // LED éteinte au démarrage

  Serial.print("Connexion au Wi-Fi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnecté ! IP de l'ESP32 : " + WiFi.localIP().toString());

  Serial.println("Chauffe du capteur PIR (30 secondes)... Ne bougez pas.");
  delay(30000);
  Serial.println("Système prêt ! En attente de mouvement...");
}

void loop() {
  int etatPIR = digitalRead(PIR_PIN);
  unsigned long tempsActuel = millis();

  // SCÉNARIO A : mouvement détecté
  if (etatPIR == HIGH) {
    chronometre = tempsActuel;

    if (!lumiereAllumee) {
      digitalWrite(LED_PIN, LOW);
      lumiereAllumee = true;
      debutMouvement = tempsActuel;
      Serial.println("\n[ALERTE] Mouvement détecté ! Lumière ON.");
      envoyerEvenementAPI("active", 0);
    }
  }

  // SCÉNARIO B : plus de mouvement depuis DELAI_ECLAIRAGE
  if (lumiereAllumee && (tempsActuel - chronometre >= DELAI_ECLAIRAGE)) {
    digitalWrite(LED_PIN, HIGH);
    lumiereAllumee = false;
    unsigned long dureeSecondes = (tempsActuel - debutMouvement) / 1000;
    Serial.println("\n[INFO] Aucun mouvement. Lumière OFF.");
    envoyerEvenementAPI("inactive", dureeSecondes);
  }

  delay(100);
}