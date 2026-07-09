/*
 * ESP32 UDP audio streamer for the always-listening HA voice trigger.
 *
 * Streams raw 16-bit mono PCM (16 kHz) from an I2S microphone (e.g. INMP441)
 * to the server over UDP. Pair this with the Python `capture.py` listener.
 *
 * Hardware: ESP32-S3 + INMP441 (or any I2S MEMS mic).
 *   INMP441  ESP32-S3
 *   WS       GPIO 15
 *   SCK      GPIO 14
 *   SD       GPIO 13
 *   L/R      GND (selects left channel)
 *
 * This is a reference sketch. Flash with the Arduino ESP32 core or ESPHome
 * external component. Set WIFI_SSID / WIFI_PASSWORD / SERVER_IP below.
 *
 * License: MIT
 */

#include <WiFi.h>
#include <driver/i2s.h>
#include <WiFiUdp.h>

// ---- Config -------------------------------------------------------------
#define WIFI_SSID     "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define SERVER_IP     "192.168.1.2"   // IP of the voice-trigger server
#define SERVER_PORT   5000            // UDP port (matches capture.py)
#define SAMPLE_RATE   16000
#define I2S_WS       15
#define I2S_SCK      14
#define I2S_SD       13
#define PACKET_SAMPLES 320            // ~20ms of audio per UDP packet

// ---- Globals ------------------------------------------------------------
WiFiUDP udp;
int16_t samples[PACKET_SAMPLES];

void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  Serial.println("WiFi connected");

  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 64,
    .use_apll = false
  };
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_in_num = I2S_SD,
    .data_out_num = I2S_PIN_NO_CHANGE
  };
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
}

void loop() {
  size_t bytes_read;
  i2s_read(I2S_NUM_0, samples, PACKET_SAMPLES * sizeof(int16_t), &bytes_read, portMAX_DELAY);
  udp.beginPacket(SERVER_IP, SERVER_PORT);
  udp.write((uint8_t*)samples, bytes_read);
  udp.endPacket();
}
