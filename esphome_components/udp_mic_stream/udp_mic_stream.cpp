#include "udp_mic_stream.h"
#include "esphome/core/log.h"

namespace esphome {
namespace udp_mic_stream {

static const char *const TAG = "udp_mic_stream";

void UDPMicStream::setup() {
  if (this->mic_ == nullptr) {
    ESP_LOGE(TAG, "Microphone not set!");
    this->mark_failed();
    return;
  }
  if (this->udp_ == nullptr) {
    ESP_LOGE(TAG, "UDP component not set!");
    this->mark_failed();
    return;
  }
  // Register a data callback that fires whenever the mic produces audio.
  this->mic_->add_data_callback([this](const std::vector<uint8_t> &data) {
    if (this->streaming_) {
      this->on_mic_data_(data);
    }
  });
  ESP_LOGCONFIG(TAG, "UDPMicStream set up (target %s:%u, %u Hz, %u ch, %u bit)",
                this->target_host_.c_str(), this->target_port_,
                this->target_rate_, this->target_channels_, this->target_bits_);
}

void UDPMicStream::loop() {
  // Nothing to do here; data arrives via callback.
}

void UDPMicStream::dump_config() {
  ESP_LOGCONFIG(TAG, "UDP Microphone Stream:");
  ESP_LOGCONFIG(TAG, "  Target: %s:%u", this->target_host_.c_str(), this->target_port_);
  ESP_LOGCONFIG(TAG, "  Sample rate: %u Hz", this->target_rate_);
  ESP_LOGCONFIG(TAG, "  Channels: %u", this->target_channels_);
  ESP_LOGCONFIG(TAG, "  Bits/sample: %u", this->target_bits_);
  ESP_LOGCONFIG(TAG, "  Packet size: %u bytes", this->packet_size_);
}

void UDPMicStream::start_stream() {
  if (this->streaming_) return;
  this->streaming_ = true;
  this->resample_buffer_.clear();
  this->out_buffer_.clear();
  this->resample_pos_ = 0;
  // Get the mic's native rate to compute the resample ratio.
  auto info = this->mic_->get_audio_stream_info();
  uint32_t src_rate = info.sample_rate;
  this->resample_ratio_ = (float)src_rate / (float)this->target_rate_;
  this->mic_->start();
  ESP_LOGI(TAG, "Streaming started (src %u Hz -> dst %u Hz)", src_rate, this->target_rate_);
}

void UDPMicStream::stop_stream() {
  if (!this->streaming_) return;
  this->streaming_ = false;
  this->mic_->stop();
  // Flush any remaining buffered samples.
  if (!this->out_buffer_.empty()) {
    this->flush_packet_();
  }
  ESP_LOGI(TAG, "Streaming stopped");
}

// Convert raw mic bytes into target-format samples and send when full.
void UDPMicStream::on_mic_data_(const std::vector<uint8_t> &data) {
  // Assume input is 32-bit stereo (4 bytes/sample, 2 channels).
  // We downmix to mono and resample to the target rate.
  const int32_t *samples = reinterpret_cast<const int32_t *>(data.data());
  size_t sample_count = data.size() / sizeof(int32_t);  // total samples (L+R interleaved)
  size_t frame_count = sample_count / 2;                // stereo frames

  for (size_t i = 0; i < frame_count; ++i) {
    int32_t left = samples[i * 2];
    int32_t right = samples[i * 2 + 1];
    int32_t mono = (left + right) / 2;  // simple downmix

    // Linear-interpolation resample: keep every Nth sample.
    this->resample_pos_ += this->resample_ratio_;
    if (this->resample_pos_ >= 1.0f) {
      this->resample_pos_ -= 1.0f;

      if (this->target_bits_ == 16) {
        // Convert 32-bit -> 16-bit (clamp)
        int32_t clamped = std::max(-32768, std::min(32767, mono >> 16));
        int16_t s = static_cast<int16_t>(clamped);
        uint8_t *p = reinterpret_cast<uint8_t *>(&s);
        this->out_buffer_.push_back(p[0]);
        this->out_buffer_.push_back(p[1]);
      } else {
        // 32-bit passthrough (target == 32)
        uint8_t *p = reinterpret_cast<uint8_t *>(&mono);
        this->out_buffer_.push_back(p[0]);
        this->out_buffer_.push_back(p[1]);
        this->out_buffer_.push_back(p[2]);
        this->out_buffer_.push_back(p[3]);
      }

      if (this->out_buffer_.size() >= this->packet_size_) {
        this->flush_packet_();
      }
    }
  }
}

void UDPMicStream::flush_packet_() {
  if (this->out_buffer_.empty()) return;
  this->send_udp_(this->out_buffer_.data(), this->out_buffer_.size());
  this->out_buffer_.clear();
}

void UDPMicStream::send_udp_(const uint8_t *data, size_t len) {
  struct sockaddr_in addr {};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(this->target_port_);
  addr.sin_addr.s_addr = inet_addr(this->target_host_.c_str());
  this->udp_->send_to(reinterpret_cast<const uint8_t *>(&addr), sizeof(addr),
                      data, len);
}

}  // namespace udp_mic_stream
}  // namespace esphome
