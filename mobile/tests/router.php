<?php
// Router dla wbudowanego serwera PHP (tylko testy i podgląd lokalny): /api/* → api/index.php.
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if (str_starts_with($path, '/api/')) { require __DIR__ . '/../api/index.php'; return true; }
return false;
