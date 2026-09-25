<?php
// Front controller API: /api/<trasa>. Każda trasa z danymi wymaga ważnej sesji albo tokenu desktopu.
declare(strict_types=1);

require_once __DIR__ . '/lib/server.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('X-Frame-Options: DENY');

function reply(int $status, array $data): void {
    http_response_code($status);
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
}

function private_dir(): string {
    $dir = getenv('BYKU_PRIVATE_DIR') ?: '';
    if ($dir === '' && is_file(__DIR__ . '/local-config.php')) $dir = (string)((require __DIR__ . '/local-config.php')['private_dir'] ?? '');
    if ($dir === '' || !is_dir($dir)) throw new HttpError(503, 'Serwer nie jest skonfigurowany (katalog prywatny)');
    $real = realpath($dir); $root = realpath((string)($_SERVER['DOCUMENT_ROOT'] ?? ''));
    if ($root && $real && str_starts_with($real . '/', rtrim($root, '/') . '/')) {
        throw new HttpError(503, 'Katalog prywatny nie może leżeć w katalogu publicznym');
    }
    return $real;
}

function json_body(): array {
    $raw = file_get_contents('php://input', false, null, 0, 2 * 1024 * 1024);
    $data = json_decode((string)$raw, true);
    if (!is_array($data)) throw new HttpError(400, 'Oczekiwano JSON');
    return $data;
}

function require_mobile_client(): void {
    // CSRF: SameSite=Strict + własny nagłówek (formularz z obcej strony go nie ustawi).
    if (($_SERVER['HTTP_X_BYKU_CLIENT'] ?? '') !== 'mobile') throw new HttpError(403, 'Brak nagłówka klienta');
}

function set_session_cookie(string $value, int $expires, bool $secure): void {
    setcookie(Server::COOKIE, $value, ['expires' => $expires, 'path' => '/', 'secure' => $secure, 'httponly' => true, 'samesite' => 'Strict']);
}

function stream_file(string $path, array $meta): void {
    $size = filesize($path);
    $ext = strtolower(pathinfo($path, PATHINFO_EXTENSION));
    $types = ['mp4' => 'video/mp4', 'mov' => 'video/quicktime', 'm4v' => 'video/mp4', 'webm' => 'video/webm', 'png' => 'image/png',
              'jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg', 'webp' => 'image/webp', 'txt' => 'text/plain; charset=utf-8'];
    header('Content-Type: ' . ($types[$ext] ?? 'application/octet-stream'));
    header('Accept-Ranges: bytes');
    header('X-Sha256: ' . $meta['sha256']);
    header('Content-Disposition: inline; filename="' . rawurlencode(basename($path)) . '"');
    $start = 0; $end = $size - 1;
    if (preg_match('/^bytes=(\d*)-(\d*)$/', $_SERVER['HTTP_RANGE'] ?? '', $m) && $size > 0) {
        if ($m[1] === '') { $start = max(0, $size - (int)$m[2]); } else { $start = (int)$m[1]; if ($m[2] !== '') $end = min((int)$m[2], $size - 1); }
        if ($start > $end) { http_response_code(416); header("Content-Range: bytes */$size"); return; }
        http_response_code(206);
        header("Content-Range: bytes $start-$end/$size");
    } else {
        http_response_code(200);
    }
    header('Content-Length: ' . ($end - $start + 1));
    if ($_SERVER['REQUEST_METHOD'] === 'HEAD') return;
    $fh = fopen($path, 'rb'); fseek($fh, $start);
    $left = $end - $start + 1;
    while ($left > 0 && !feof($fh)) { $chunk = fread($fh, (int)min(262144, $left)); echo $chunk; $left -= strlen($chunk); flush(); }
    fclose($fh);
}

try {
    $route = trim((string)($_GET['route'] ?? ''), '/');
    if ($route === '') {
        $path = (string)parse_url((string)($_SERVER['REQUEST_URI'] ?? ''), PHP_URL_PATH);
        $pos = strpos($path, '/api/');
        $route = $pos === false ? '' : trim(substr($path, $pos + 5), '/');
    }
    $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
    $server = new Server(private_dir());
    $token = $_COOKIE[Server::COOKIE] ?? null;
    $secure = (bool)(getenv('BYKU_INSECURE_COOKIE') ? false : true);
    $ip = (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown');

    switch ("$method $route") {
        case 'POST login':
            require_mobile_client();
            $body = json_body();
            $result = $server->login((string)($body['login'] ?? ''), (string)($body['password'] ?? ''), $ip);
            set_session_cookie($result['token'], 0, $secure);
            reply(200, $result['session']);
            break;
        case 'POST logout':
            require_mobile_client();
            $server->logout($token);
            set_session_cookie('', time() - 3600, $secure);
            reply(200, ['authenticated' => false]);
            break;
        case 'GET session':
            try { reply(200, $server->requireSession($token)); }
            catch (HttpError $e) { reply(200, ['authenticated' => false, 'reason' => $e->getMessage()]); }
            break;
        case 'GET index':
            $server->requireSession($token);
            reply(200, $server->index());
            break;
        case 'GET file':
        case 'HEAD file':
            $server->requireSession($token);
            [$path, $meta] = $server->filePath((string)($_GET['package'] ?? ''), (string)($_GET['rev'] ?? ''), (string)($_GET['name'] ?? ''));
            header_remove('Content-Type');
            stream_file($path, $meta);
            break;
        case 'POST events':
            require_mobile_client();
            $session = $server->requireSession($token);
            $body = json_body();
            reply(200, $server->addEvents(is_array($body['events'] ?? null) ? $body['events'] : [], $session['user']));
            break;
        case 'PUT upload/file':
            $server->requireUploader($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? null);
            reply(200, $server->uploadFile((string)($_GET['package'] ?? ''), (string)($_GET['rev'] ?? ''), (string)($_GET['name'] ?? ''),
                strtolower((string)($_SERVER['HTTP_X_SHA256'] ?? '')), 'php://input'));
            break;
        case 'POST upload/commit':
            $server->requireUploader($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? null);
            reply(200, $server->commit(json_body()));
            break;
        case 'GET events/export':
            $server->requireUploader($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? null);
            reply(200, $server->exportEvents());
            break;
        default:
            reply(404, ['error' => 'Nieznany adres']);
    }
} catch (HttpError $e) {
    reply($e->status, ['error' => $e->getMessage()]);
} catch (Throwable $e) {
    error_log('byku-mobile: ' . $e->getMessage());
    reply(500, ['error' => 'Błąd serwera']);
}
