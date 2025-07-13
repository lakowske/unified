<?php
header('Content-Type: text/plain');

echo "Environment Variables Debug:\n";
echo "DB_HOST: " . ($_ENV['DB_HOST'] ?? 'NOT SET') . "\n";
echo "DB_PORT: " . ($_ENV['DB_PORT'] ?? 'NOT SET') . "\n";
echo "DB_NAME: " . ($_ENV['DB_NAME'] ?? 'NOT SET') . "\n";
echo "DB_USER: " . ($_ENV['DB_USER'] ?? 'NOT SET') . "\n";
echo "DB_PASSWORD: " . ($_ENV['DB_PASSWORD'] ?? 'NOT SET') . "\n";

echo "\nAll Environment Variables:\n";
foreach ($_ENV as $key => $value) {
    if (strpos($key, 'DB_') === 0 || strpos($key, 'HOST') !== false) {
        echo "$key = $value\n";
    }
}

echo "\nTesting PDO connection:\n";
$dsn = sprintf(
    'pgsql:host=%s;port=%s;dbname=%s;options=--search_path=unified,public',
    $_ENV['DB_HOST'] ?? 'localhost',
    $_ENV['DB_PORT'] ?? '5432',
    $_ENV['DB_NAME'] ?? 'unified_dev'
);

echo "DSN: $dsn\n";

try {
    $pdo = new PDO($dsn, $_ENV['DB_USER'] ?? 'poststack', $_ENV['DB_PASSWORD'] ?? 'poststack_dev');
    echo "Database connection: SUCCESS\n";
} catch (Exception $e) {
    echo "Database connection: FAILED - " . $e->getMessage() . "\n";
}
?>
