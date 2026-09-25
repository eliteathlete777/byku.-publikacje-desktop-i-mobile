<?php
// BYKU.PUBLIKACJE MOBILE — serwer (Hostinger, PHP >= 8.1).
// Dane i konfiguracja leżą POZA katalogiem publicznym (katalog prywatny).
declare(strict_types=1);

require_once __DIR__ . '/contract.php';

final class HttpError extends Exception {
    public function __construct(public int $status, string $message) { parent::__construct($message); }
}

final class Server {
    public const COOKIE = 'byku_session';
    public const EVENT_TYPES = ['downloaded', 'caption_copied', 'hashtags_copied', 'instagram_opened', 'manual_check'];
    private array $config;
    private int $now;

    public function __construct(private string $private, ?int $now = null) {
        $file = $private . '/config.php';
        if (!is_file($file)) throw new HttpError(503, 'Serwer nie jest skonfigurowany');
        $this->config = require $file;
        $this->now = $now ?? time();
        foreach (['sessions', 'packages', 'staging', 'ratelimit'] as $dir) {
            if (!is_dir("$private/$dir")) mkdir("$private/$dir", 0700, true);
        }
    }

    public function now(): int { return (int)(getenv('BYKU_TEST_NOW') ?: $this->now); }

    // ---------------- sesje ----------------
    private function sessionFile(string $token): string {
        return $this->private . '/sessions/' . hash('sha256', $token) . '.json';
    }

    public function login(string $login, string $password, string $ip): array {
        $this->throttle($ip);
        $user = $this->config['users'][$login] ?? null;
        // Stały czas weryfikacji także dla nieistniejącego loginu.
        $hash = $user['password_hash'] ?? '$2y$12$xoxBc7cXudCRoA30jvPMsOKma9iEl1wxODGJT9AfUQmLyR71QfbKu';
        $ok = password_verify($password, $hash) && $user !== null;
        if (!$ok) { $this->fail($ip); throw new HttpError(401, 'Nieprawidłowy login lub hasło'); }
        $this->clearFails($ip);
        $token = bin2hex(random_bytes(32));
        $session = ['user' => $login, 'created' => $this->now(), 'last_seen' => $this->now()];
        file_put_contents($this->sessionFile($token), json_encode($session), LOCK_EX);
        return ['token' => $token, 'session' => $this->describe($session)];
    }

    private function describe(array $s): array {
        $idle = (int)($this->config['session_idle'] ?? 43200);
        $abs = (int)($this->config['session_absolute'] ?? 604800);
        return ['authenticated' => true, 'user' => $s['user'],
                'expires_at' => gmdate('Y-m-d\TH:i:s\Z', min($s['last_seen'] + $idle, $s['created'] + $abs))];
    }

    /** Zwraca sesję albo rzuca 401 — każdy dostęp do danych przechodzi tędy. */
    public function requireSession(?string $token): array {
        if (!$token || !preg_match('/^[a-f0-9]{64}$/', $token)) throw new HttpError(401, 'Zaloguj się');
        $file = $this->sessionFile($token);
        $raw = is_file($file) ? json_decode((string)file_get_contents($file), true) : null;
        if (!is_array($raw)) throw new HttpError(401, 'Sesja nie istnieje. Zaloguj się ponownie');
        $idle = (int)($this->config['session_idle'] ?? 43200);
        $abs = (int)($this->config['session_absolute'] ?? 604800);
        if ($this->now() > $raw['last_seen'] + $idle || $this->now() > $raw['created'] + $abs || !isset($this->config['users'][$raw['user']])) {
            @unlink($file);
            throw new HttpError(401, 'Sesja wygasła. Zaloguj się ponownie');
        }
        if ($this->now() - $raw['last_seen'] > 60) {
            $raw['last_seen'] = $this->now();
            file_put_contents($file, json_encode($raw), LOCK_EX);
        }
        return $this->describe($raw);
    }

    public function logout(?string $token): void {
        if ($token && preg_match('/^[a-f0-9]{64}$/', $token)) @unlink($this->sessionFile($token));
    }

    public function requireUploader(?string $authorization): void {
        $expected = (string)($this->config['upload_token_sha256'] ?? '');
        if (!preg_match('/^Bearer\s+(\S+)$/', (string)$authorization, $m) || $expected === ''
            || !hash_equals($expected, hash('sha256', $m[1]))) {
            throw new HttpError(401, 'Nieprawidłowy token wysyłki');
        }
    }

    // ---------------- limit prób logowania ----------------
    private function rateFile(string $ip): string { return $this->private . '/ratelimit/' . hash('sha256', $ip) . '.json'; }
    private function attempts(string $ip): array {
        $f = $this->rateFile($ip);
        $list = is_file($f) ? (json_decode((string)file_get_contents($f), true) ?: []) : [];
        return array_values(array_filter($list, fn($t) => $t > $this->now() - 900));
    }
    private function throttle(string $ip): void {
        if (count($this->attempts($ip)) >= 5) throw new HttpError(429, 'Za dużo prób. Odczekaj 15 minut');
    }
    private function fail(string $ip): void {
        $list = $this->attempts($ip); $list[] = $this->now();
        file_put_contents($this->rateFile($ip), json_encode($list), LOCK_EX);
    }
    private function clearFails(string $ip): void { @unlink($this->rateFile($ip)); }

    // ---------------- paczki ----------------
    private static function packageId(string $id): string {
        if (!preg_match('/^(atlet|rigger)--[^\/\\\\]{1,180}$/', $id) || str_contains($id, '..') || preg_match('/[\x00-\x1f]/', $id)) {
            throw new HttpError(400, 'Nieprawidłowy identyfikator paczki');
        }
        return $id;
    }
    private static function revision(string $rev): string {
        if (!preg_match('/^[a-f0-9]{64}$/', $rev)) throw new HttpError(400, 'Nieprawidłowa rewizja');
        return $rev;
    }
    private static function fileName(string $name): string {
        if (!byku_safe_name($name)) throw new HttpError(400, 'Nieprawidłowa nazwa pliku');
        return $name;
    }
    private function pkgDir(string $id): string { return $this->private . '/packages/' . rawurlencode($id); }
    private function current(string $id): ?array {
        $f = $this->pkgDir($id) . '/current.json';
        return is_file($f) ? json_decode((string)file_get_contents($f), true) : null;
    }

    public function index(): array {
        $out = [];
        foreach (glob($this->private . '/packages/*/current.json') ?: [] as $f) {
            $m = json_decode((string)file_get_contents($f), true);
            if (!is_array($m)) continue;
            $m['base_url'] = 'api/file?' . http_build_query(['package' => $m['package_id'], 'rev' => $m['content_revision']]);
            $out[] = $m;
        }
        usort($out, fn($a, $b) => strcmp($b['exported_at'], $a['exported_at']));
        return ['schema_version' => BYKU_SCHEMA_VERSION, 'generated_at' => gmdate('Y-m-d\TH:i:s\Z', $this->now()), 'packages' => $out];
    }

    /** Ścieżka pliku aktualnej rewizji; starsze rewizje nie są wydawane. */
    public function filePath(string $id, string $rev, string $name): array {
        $id = self::packageId($id); $rev = self::revision($rev); $name = self::fileName($name);
        $current = $this->current($id);
        if (!$current || $current['content_revision'] !== $rev) throw new HttpError(410, 'Ta wersja paczki nie jest już aktualna. Odśwież');
        foreach ($current['files'] as $f) {
            if ($f['name'] === $name) {
                $path = $this->pkgDir($id) . '/' . $rev . '/' . $name;
                if (!is_file($path)) throw new HttpError(404, 'Brak pliku');
                return [$path, $f];
            }
        }
        throw new HttpError(404, 'Plik nie należy do paczki');
    }

    public function uploadFile(string $id, string $rev, string $name, string $sha, string $source): array {
        $id = self::packageId($id); $rev = self::revision($rev); $name = self::fileName($name);
        if (!preg_match('/^[a-f0-9]{64}$/', $sha)) throw new HttpError(400, 'Brak nagłówka X-Sha256');
        $dir = $this->private . '/staging/' . rawurlencode($id) . '/' . $rev;
        if (!is_dir($dir)) mkdir($dir, 0700, true);
        $tmp = "$dir/.$name.part";
        $in = fopen($source, 'rb'); $out = fopen($tmp, 'wb');
        $size = stream_copy_to_stream($in, $out); fclose($in); fclose($out);
        if (!hash_equals($sha, hash_file('sha256', $tmp))) { @unlink($tmp); throw new HttpError(422, "Suma SHA-256 pliku $name się nie zgadza"); }
        rename($tmp, "$dir/$name");
        return ['ok' => true, 'name' => $name, 'size' => $size];
    }

    public function commit(array $manifest): array {
        $errors = byku_validate_manifest($manifest);
        if ($errors) throw new HttpError(422, 'Manifest niezgodny z kontraktem: ' . implode('; ', array_column($errors, 'message')));
        $id = self::packageId($manifest['package_id']); $rev = $manifest['content_revision'];
        $current = $this->current($id);
        if ($current && $current['content_revision'] === $rev) return ['ok' => true, 'state' => 'current', 'duplicate' => true];
        if ($current && strcmp($current['exported_at'], $manifest['exported_at']) > 0) {
            throw new HttpError(409, 'Na serwerze jest nowsza wersja tej paczki — starsza jej nie zastąpi');
        }
        $staging = $this->private . '/staging/' . rawurlencode($id) . '/' . $rev;
        foreach ($manifest['files'] as $f) {
            $p = $staging . '/' . $f['name'];
            if (!is_file($p)) throw new HttpError(422, "Brak wysłanego pliku {$f['name']}");
            if (filesize($p) !== $f['size'] || !hash_equals($f['sha256'], hash_file('sha256', $p))) throw new HttpError(422, "Plik {$f['name']} nie zgadza się z manifestem");
        }
        $pkg = $this->pkgDir($id);
        if (!is_dir($pkg)) mkdir($pkg, 0700, true);
        $target = "$pkg/$rev";
        if (is_dir($target)) self::rmtree($target);
        rename($staging, $target);
        file_put_contents("$target/manifest.json", json_encode($manifest, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
        file_put_contents("$pkg/current.json.tmp", json_encode($manifest, JSON_UNESCAPED_UNICODE));
        rename("$pkg/current.json.tmp", "$pkg/current.json");
        foreach (glob("$pkg/*", GLOB_ONLYDIR) ?: [] as $old) if (basename($old) !== $rev) self::rmtree($old);
        return ['ok' => true, 'state' => $current ? 'newer' : 'new'];
    }

    // ---------------- zdarzenia telefonu ----------------
    public function addEvents(array $events, string $user): array {
        $file = $this->private . '/events.jsonl';
        $fh = fopen($file, 'c+'); flock($fh, LOCK_EX);
        $seen = [];
        while (($line = fgets($fh)) !== false) { $e = json_decode($line, true); if (isset($e['event_id'])) $seen[$e['event_id']] = true; }
        $accepted = 0; $skipped = 0;
        fseek($fh, 0, SEEK_END);
        foreach (array_slice($events, 0, 500) as $e) {
            $id = is_array($e) ? (string)($e['event_id'] ?? '') : '';
            $type = is_array($e) ? ($e['type'] ?? '') : '';
            if (!preg_match('/^[A-Za-z0-9-]{8,64}$/', $id) || !in_array($type, self::EVENT_TYPES, true) || isset($seen[$id])) { $skipped++; continue; }
            $row = ['event_id' => $id, 'type' => $type, 'package_id' => (string)($e['package_id'] ?? ''), 'post_id' => (string)($e['post_id'] ?? ''),
                    'brand' => (string)($e['brand'] ?? ''), 'occurred_at' => (string)($e['occurred_at'] ?? ''), 'user' => $user,
                    'received_at' => gmdate('Y-m-d\TH:i:s\Z', $this->now())];
            fwrite($fh, json_encode($row, JSON_UNESCAPED_UNICODE) . "\n");
            $seen[$id] = true; $accepted++;
        }
        flock($fh, LOCK_UN); fclose($fh);
        return ['accepted' => $accepted, 'skipped' => $skipped];
    }

    public function exportEvents(): array {
        $file = $this->private . '/events.jsonl';
        $rows = [];
        if (is_file($file)) foreach (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) { $r = json_decode($line, true); if ($r) $rows[] = $r; }
        return ['events' => $rows];
    }

    private static function rmtree(string $dir): void {
        foreach (scandir($dir) ?: [] as $f) {
            if ($f === '.' || $f === '..') continue;
            $p = "$dir/$f"; is_dir($p) ? self::rmtree($p) : unlink($p);
        }
        rmdir($dir);
    }
}
