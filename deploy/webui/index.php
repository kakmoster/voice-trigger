<?php
// Voice Trigger — configuration web UI (index).
// Reachable at http://<host>:8080/
// Secrets are written to ../secrets/.env (blocked from web access).

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

$msg = '';
if (isset($_GET['saved'])) $msg = 'Settings saved.';
elseif (isset($_GET['test'])) $msg = htmlspecialchars($_GET['test']);
elseif (isset($_GET['restarted'])) $msg = 'App restarted.';
?>
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Voice Trigger — Config</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  h1 { font-size: 1.4rem; }
  .row { margin-bottom: 1rem; }
  label { display: block; margin: .5rem 0 .2rem; font-weight: 600; }
  input { width: 100%; padding: .55rem; box-sizing: border-box; border: 1px solid #ccc; border-radius: 6px; }
  .hint { font-size: .8rem; color: #666; margin-top: .2rem; }
  button { margin-top: 1rem; padding: .6rem 1.3rem; border: 0; border-radius: 6px; background: #2b6cb0; color: #fff; cursor: pointer; }
  a.btn { display: inline-block; margin-top: 1rem; padding: .6rem 1.3rem; border-radius: 6px; background: #555; color: #fff; text-decoration: none; }
  .msg { color: #1a7f37; font-weight: 600; }
  .panel { margin-top: 2rem; border-top: 1px solid #eee; padding-top: 1rem; }
  .actions { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }
  pre { background:#111; color:#0f0; padding:1rem; border-radius:8px; overflow:auto; white-space:pre-wrap; max-height:320px; }
</style>
</head>
<body>
  <h1>Voice Trigger — Configuration</h1>
  <?php if ($msg): ?><p class="msg"><?= $msg ?></p><?php endif; ?>
  <form method="post" action="save.php">
    <div class="row">
      <label>Home Assistant URL</label>
      <input name="ha_url" value="<?= htmlspecialchars($config['HA_URL'] ?? '') ?>" placeholder="http://192.168.1.2:8123">
    </div>
    <div class="row">
      <label>Home Assistant Long-Lived Token</label>
      <input name="ha_token" placeholder="leave empty to keep current">
      <div class="hint">Create in HA: Profile &rarr; Long-lived access tokens.</div>
    </div>
    <div class="row">
      <label>Ollama URL</label>
      <input name="ollama_url" value="<?= htmlspecialchars($config['OLLAMA_URL'] ?? '') ?>" placeholder="http://192.168.1.2:11434">
    </div>
    <div class="row">
      <label>Ollama API Token</label>
      <input name="ollama_token" placeholder="optional / leave empty to keep current">
    </div>
    <div class="actions">
      <button type="submit">Save</button>
      <a class="btn" href="test.php">Test HA connection</a>
    </div>
  </form>

  <div class="panel">
    <h2>Service control</h2>
    <div class="actions">
      <a class="btn" href="action.php?action=restart">Restart / Reload App</a>
      <a class="btn" href="action.php?action=logs&n=100">View Debug Log</a>
    </div>
    <p class="hint">Restart reloads the app with the latest saved settings. The debug log shows the app's output (model download, STT errors, HA timeouts).</p>
  </div>
</body>
</html>
