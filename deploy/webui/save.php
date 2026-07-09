<?php
// Voice Trigger — save configuration.
// Writes ../secrets/.env. Token fields left empty keep the existing value.

$env_path = '/var/www/html/secrets/.env';
$dir = dirname($env_path);
if (!is_dir($dir)) mkdir($dir, 0700, true);

$existing = [];
if (file_exists($env_path)) {
    foreach (file($env_path) as $line) {
        $line = trim($line);
        if ($line === '' || strpos($line, '#') === 0) continue;
        if (strpos($line, '=') !== false) {
            list($k, $v) = explode('=', $line, 2);
            $existing[trim($k)] = trim($v, '"\'');
        }
    }
}

function get_post($k) { return trim((string)($_POST[$k] ?? '')); }

$ha_url = get_post('ha_url');
$ha_token = get_post('ha_token');
$ollama_url = get_post('ollama_url');
$ollama_token = get_post('ollama_token');

if ($ha_token === '' && isset($existing['HA_TOKEN'])) $ha_token = $existing['HA_TOKEN'];
if ($ollama_token === '' && isset($existing['OLLAMA_TOKEN'])) $ollama_token = $existing['OLLAMA_TOKEN'];

if ($ha_url !== '' && !filter_var($ha_url, FILTER_VALIDATE_URL)) {
    header('Location: index.php?test=' . urlencode('Invalid HA URL'));
    exit;
}

$lines = [
    "# Voice Trigger configuration — local only, do not commit",
    "HA_URL=" . escapeshellarg($ha_url),
    "HA_TOKEN=" . escapeshellarg($ha_token),
    "OLLAMA_URL=" . escapeshellarg($ollama_url),
    "OLLAMA_TOKEN=" . escapeshellarg($ollama_token),
];
file_put_contents($env_path, implode("\n", $lines) . "\n");
chmod($env_path, 0644);

header('Location: index.php?saved=1');
exit;
