<?php
// Tworzy konfigurację serwera w KATALOGU PRYWATNYM (poza public_html). Tylko z konsoli (SSH).
// Użycie: php api/tools/make-config.php /home/UZYTKOWNIK/byku-mobile-private LOGIN
// Hasło jest pytane bez echa. Token desktopu jest wypisywany RAZ — wpisz go do desktop/.env.
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
[$_, $dir, $login] = $argv + [null, null, null];
if (!$dir || !$login || !preg_match('/^[a-z0-9._-]{3,32}$/i', $login)) { fwrite(STDERR, "Użycie: php make-config.php KATALOG_PRYWATNY LOGIN\n"); exit(1); }
$password = getenv('BYKU_PASSWORD') ?: '';
if ($password === '') {
    fwrite(STDOUT, "Hasło (min. 12 znaków): "); system('stty -echo'); $password = trim((string)fgets(STDIN)); system('stty echo'); fwrite(STDOUT, "\n");
}
if (strlen($password) < 12) { fwrite(STDERR, "Hasło musi mieć co najmniej 12 znaków\n"); exit(1); }
if (!is_dir($dir)) mkdir($dir, 0700, true);
$file = rtrim($dir, '/') . '/config.php';
$config = is_file($file) ? require $file : ['users' => [], 'session_idle' => 43200, 'session_absolute' => 604800];
$config['users'][$login] = ['password_hash' => password_hash($password, PASSWORD_DEFAULT)];
$token = getenv('BYKU_UPLOAD_TOKEN') ?: '';
if ($token === '' && empty($config['upload_token_sha256'])) $token = bin2hex(random_bytes(32));
if ($token !== '') $config['upload_token_sha256'] = hash('sha256', $token);
file_put_contents($file, "<?php\nreturn " . var_export($config, true) . ";\n", LOCK_EX);
chmod($file, 0600);
file_put_contents(rtrim($dir, '/') . '/.htaccess', "Require all denied\nDeny from all\n");
fwrite(STDOUT, "Zapisano: $file (użytkownik: $login)\n");
if ($token !== '') fwrite(STDOUT, "TOKEN DESKTOPU (zapisz w desktop/.env jako BYKU_MOBILE_UPLOAD_TOKEN=...):\n$token\n");
