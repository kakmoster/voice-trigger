<?php
// Voice Trigger — test Home Assistant connection using stored credentials.

$env_path = '/var/www/html/secrets/.env';
$config = [];
if (file_exists($env_path)) {
    foreach (file($env_path) as $line) {
        $line = trim($line);
        if ($line === '' || strpos($line, '#') === 0) continue;
        if (strpos($line, '=') !== false) {
            list($k, $v) = explode('=', $line, 2);
            $config[trim($k)] = trim($v, '"\'');
        }
    }
}

$url = rtrim($config['HA_URL'] ?? '', '/') . '/api/';
$token = $config['HA_TOKEN'] ?? '';

if (!$url || !$token) {
    header('Location: index.php?test=' . urlencode('Missing HA_URL or HA_TOKEN'));
    exit;
}

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_HTTPHEADER => ["Authorization: Bearer $token"],
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 5,
    CURLOPT_SSL_VERIFYPEER => false,
]);
$response = curl_exec($ch);
$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$err = curl_error($ch);
curl_close($ch);

if ($code === 200) $out = 'OK - HA reachable (HTTP 200)';
elseif ($err) $out = 'Connection error: ' . $err;
else $out = "Failed - HTTP $code";

header('Location: index.php?test=' . urlencode($out));
exit;
