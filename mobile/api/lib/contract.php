<?php
// Walidator kontraktu v2 (contract/KONTRAKT.md). Musi dawać ten sam wynik co
// desktop/backend/contract.py i mobile/src/contract.js dla contract/fixtures/cases.json.
declare(strict_types=1);

const BYKU_SCHEMA_VERSION = 2;
const BYKU_BRANDS = ['atlet', 'rigger'];
const BYKU_EVIDENCE = ['unknown', 'scheduled', 'published', 'failed'];
const BYKU_ROLES = ['video', 'slide', 'thumbnail', 'caption', 'hashtags'];
const BYKU_TIKTOK = ['published', 'scheduled', 'manual_checked'];

function byku_safe_name($name): bool {
    return is_string($name) && $name !== '' && $name !== 'manifest.json' && $name[0] !== '.'
        && strpbrk($name, "/\\") === false && strpos($name, '..') === false && strlen($name) <= 180
        && preg_match('/[\x00-\x1f]/', $name) !== 1;
}

function byku_is_int($v): bool { return is_int($v); }

/** @return array<int, array{code:string, message:string}> */
function byku_validate_manifest($m): array {
    $errors = [];
    $err = function (string $code, string $message) use (&$errors) { $errors[] = ['code' => $code, 'message' => $message]; };
    if (!is_array($m) || array_is_list($m)) return [['code' => 'FIELD', 'message' => 'Brak manifestu']];
    if (($m['schema_version'] ?? null) !== BYKU_SCHEMA_VERSION) $err('SCHEMA', 'Nieobsługiwana wersja schematu');
    $brand = $m['brand'] ?? null; $post = $m['post_id'] ?? null;
    if (!in_array($brand, BYKU_BRANDS, true)) $err('BRAND', 'Nieznana marka');
    if (($m['channel'] ?? null) !== 'instagram') $err('CHANNEL', 'Niewłaściwy kanał');
    if (!is_string($post) || trim($post) === '' || !byku_safe_name($post)) $err('FIELD', 'Brak lub zły post_id');
    elseif (($m['package_id'] ?? null) !== ((string)$brand) . '--' . $post) $err('FIELD', 'package_id nie zgadza się z marką i post_id');
    if (!is_string($m['content_revision'] ?? null) || !preg_match('/^[a-f0-9]{64}$/', $m['content_revision'])) $err('FIELD', 'content_revision musi być sumą SHA-256');
    $exp = $m['exported_at'] ?? null;
    if (!is_string($exp) || !preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/', $exp) || strtotime($exp) === false) $err('FIELD', 'exported_at musi być datą ISO UTC');
    foreach (['caption', 'hashtags', 'location', 'title'] as $k) if (array_key_exists($k, $m) && !is_string($m[$k])) $err('FIELD', "$k musi być tekstem");
    $type = $m['type'] ?? null;
    if (!in_array($type, ['reel', 'carousel'], true)) $err('TYPE', 'Nieznany typ paczki');

    $files = $m['files'] ?? null;
    if (!is_array($files) || !array_is_list($files) || count($files) === 0) { $err('FILES', 'Brak listy plików'); $files = []; }
    $names = []; $roles = array_fill_keys(BYKU_ROLES, []);
    foreach ($files as $f) {
        if (!is_array($f)) { $err('FILE_NAME', 'Nieprawidłowy wpis pliku'); continue; }
        $name = $f['name'] ?? null;
        if (!byku_safe_name($name)) $err('FILE_NAME', 'Niedozwolona nazwa pliku');
        elseif (isset($names[$name])) $err('FILE_NAME', "Powtórzony plik: $name");
        else $names[$name] = true;
        $role = $f['role'] ?? null;
        if (!in_array($role, BYKU_ROLES, true)) $err('FILE_NAME', 'Nieznana rola pliku');
        else $roles[$role][] = $f;
        if (!is_string($f['sha256'] ?? null) || !preg_match('/^[a-f0-9]{64}$/', $f['sha256'])) $err('FILE_HASH', 'Zła suma SHA-256');
        if (!byku_is_int($f['size'] ?? null) || $f['size'] < 0) $err('FILE_HASH', 'Zły rozmiar pliku');
    }
    if ($files) {
        foreach (['thumbnail' => 'miniatury', 'caption' => 'opisu', 'hashtags' => 'hashtagów'] as $r => $label)
            if (count($roles[$r]) !== 1) $err('ROLE_MISSING', "Paczka musi mieć dokładnie jeden plik $label");
        if ($type === 'reel' && !$roles['video']) $err('ROLE_MISSING', 'Rolka nie ma pliku wideo');
        if ($type === 'carousel') {
            if (count($roles['slide']) < 2) $err('ROLE_MISSING', 'Karuzela musi mieć co najmniej 2 slajdy');
            $orders = array_map(fn($s) => $s['order'] ?? null, $roles['slide']);
            $allInt = !in_array(false, array_map('byku_is_int', $orders), true);
            if (!$allInt || count(array_unique($orders)) !== count($orders)) $err('ORDER', 'Slajdy muszą mieć unikalną kolejność');
        }
    }
    $p = $m['platforms'] ?? null;
    if (!is_array($p)) $err('PLATFORMS', 'Brak stanów platform');
    else foreach (['tiktok', 'instagram', 'facebook'] as $ch) {
        $x = $p[$ch] ?? null;
        if (!is_array($x) || !in_array($x['evidence'] ?? null, BYKU_EVIDENCE, true) || !is_bool($x['manual_checked'] ?? null)) $err('PLATFORMS', "Zły stan platformy: $ch");
    }
    $t = $m['transfer'] ?? null;
    if (!is_array($t) || ($t['from'] ?? null) !== 'tiktok' || ($t['to'] ?? null) !== 'instagram'
        || !in_array($t['tiktok'] ?? null, BYKU_TIKTOK, true) || ($t['instagram'] ?? null) !== 'pending')
        $err('TRANSFER', 'Paczka musi opisywać transfer: TikTok gotowy, Instagram oczekuje');
    return $errors;
}
