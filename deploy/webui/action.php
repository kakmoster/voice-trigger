<?php
// Voice Trigger — restart/reload the app service via docker compose.
// The host docker socket is mounted into this container (see compose).

function docker_compose($args) {
    $compose = '/var/www/html';
    $cmd = "docker compose -f $compose/docker-compose.yml $args 2>&1";
    $out = shell_exec($cmd);
    return $out !== null ? $out : 'Failed to run docker compose.';
}

$action = $_GET['action'] ?? '';
if ($action === 'restart') {
    $result = docker_compose('restart app');
    $msg = 'App restarted.';
} elseif ($action === 'logs') {
    $lines = (int)($_GET['n'] ?? 100);
    $result = docker_compose("logs --tail=$lines app");
    $msg = "Last $lines log lines.";
} else {
    $msg = 'Unknown action.';
    $result = '';
}
?>
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Voice Trigger — Result</title>
<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem;color:#222}pre{background:#111;color:#0f0;padding:1rem;border-radius:8px;overflow:auto;white-space:pre-wrap}a{color:#2b6cb0}</style>
</head><body>
<h1>Voice Trigger — Action</h1>
<p class="msg"><?= htmlspecialchars($msg) ?></p>
<pre><?= htmlspecialchars($result) ?></pre>
<p><a href="index.php">← Back to settings</a></p>
</body></html>
