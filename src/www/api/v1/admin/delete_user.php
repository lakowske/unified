<?php
/**
 * User Deletion API Endpoint
 *
 * Deletes users from the unified.users table with API key authentication.
 * Used by unified service operations for user management.
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-API-Key');

// Handle preflight requests
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Only allow DELETE requests
if ($_SERVER['REQUEST_METHOD'] !== 'DELETE') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed. Use DELETE.']);
    exit();
}

/**
 * Validate API key from request headers
 */
function validateApiKey() {
    $api_key_file = '/var/local/unified_api_key';

    if (!file_exists($api_key_file)) {
        error_log("API key file not found: $api_key_file");
        return false;
    }

    $stored_key = trim(file_get_contents($api_key_file));
    if (!$stored_key) {
        error_log("Empty API key in file: $api_key_file");
        return false;
    }

    // Check X-API-Key header
    $headers = getallheaders();
    if (isset($headers['X-API-Key'])) {
        return hash_equals($stored_key, $headers['X-API-Key']);
    }

    // Check Authorization header (Bearer token)
    if (isset($headers['Authorization'])) {
        $auth_header = $headers['Authorization'];
        if (preg_match('/Bearer\s+(.+)/', $auth_header, $matches)) {
            return hash_equals($stored_key, $matches[1]);
        }
    }

    return false;
}

try {
    // Validate API key
    if (!validateApiKey()) {
        http_response_code(401);
        echo json_encode(['error' => 'Invalid or missing API key']);
        exit();
    }

    // Parse request body or URL parameter
    $input = json_decode(file_get_contents('php://input'), true);
    $user_id = null;
    $username = null;

    // Check JSON body first
    if ($input && isset($input['user_id'])) {
        $user_id = intval($input['user_id']);
    } elseif ($input && isset($input['username'])) {
        $username = trim($input['username']);
    }

    // Check URL parameters if not in body
    if (!$user_id && !$username) {
        if (isset($_GET['user_id'])) {
            $user_id = intval($_GET['user_id']);
        } elseif (isset($_GET['username'])) {
            $username = trim($_GET['username']);
        }
    }

    if (!$user_id && !$username) {
        http_response_code(400);
        echo json_encode(['error' => 'Either user_id or username is required']);
        exit();
    }

    // Connect to database
    $dsn = sprintf(
        'pgsql:host=%s;port=%s;dbname=%s;options=--search_path=unified,public',
        $_SERVER['DB_HOST'] ?? 'localhost',
        $_SERVER['DB_PORT'] ?? '5432',
        $_SERVER['DB_NAME'] ?? 'unified_dev'
    );

    $pdo = new PDO($dsn, $_SERVER['DB_USER'] ?? 'unified', $_SERVER['DB_PASSWORD'] ?? 'unified_dev');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // Find the user to delete
    if ($user_id) {
        $stmt = $pdo->prepare('SELECT id, username, email FROM users WHERE id = ?');
        $stmt->execute([$user_id]);
    } else {
        $stmt = $pdo->prepare('SELECT id, username, email FROM users WHERE username = ?');
        $stmt->execute([$username]);
    }

    $user = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$user) {
        http_response_code(404);
        echo json_encode(['error' => 'User not found']);
        exit();
    }

    // Begin transaction for cascading delete
    $pdo->beginTransaction();

    try {
        // Delete user (CASCADE will handle passwords, roles, etc.)
        $stmt = $pdo->prepare('DELETE FROM users WHERE id = ?');
        $stmt->execute([$user['id']]);

        // Commit transaction
        $pdo->commit();

    } catch (Exception $e) {
        $pdo->rollBack();
        throw $e;
    }

    // Log the deletion
    error_log("User deleted successfully: username={$user['username']}, id={$user['id']}");

    // Return success response
    http_response_code(200);
    echo json_encode([
        'success' => true,
        'message' => 'User deleted successfully',
        'deleted_user' => [
            'id' => $user['id'],
            'username' => $user['username'],
            'email' => $user['email']
        ]
    ]);

} catch (PDOException $e) {
    error_log("Database error in delete_user.php: " . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Database error occurred']);
} catch (Exception $e) {
    error_log("General error in delete_user.php: " . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Internal server error']);
}
?>
