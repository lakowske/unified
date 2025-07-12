<?php
// Health check endpoint for Docker container
header('Content-Type: application/json');

$health = [
    'status' => 'healthy',
    'timestamp' => date('c'),
    'service' => 'unified-apache',
    'version' => '1.0.0'
];

// Check database connection if environment variables are available
if (isset($_SERVER['DB_HOST'])) {
    try {
        $dsn = sprintf(
            'pgsql:host=%s;port=%s;dbname=%s',
            $_SERVER['DB_HOST'],
            $_SERVER['DB_PORT'] ?? '5432',
            $_SERVER['DB_NAME']
        );

        $pdo = new PDO($dsn, $_SERVER['DB_USER'], $_SERVER['DB_PASSWORD']);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

        // Test query to unified schema
        $stmt = $pdo->query('SELECT COUNT(*) as user_count FROM unified.users WHERE is_active = true');
        $result = $stmt->fetch(PDO::FETCH_ASSOC);

        $health['database'] = [
            'status' => 'connected',
            'active_users' => (int)$result['user_count']
        ];
    } catch (Exception $e) {
        $health['database'] = [
            'status' => 'error',
            'error' => $e->getMessage()
        ];
        $health['status'] = 'degraded';
    }
}

http_response_code(200);
echo json_encode($health, JSON_PRETTY_PRINT);
?>
