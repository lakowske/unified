<?php
/**
 * User Creation API Endpoint
 *
 * Creates new users in the unified.users table with API key authentication.
 * Used by poststack service operations for user management.
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-API-Key');

// Handle preflight requests
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Only allow POST requests
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed. Use POST.']);
    exit();
}

/**
 * Validate API key from request headers or body
 */
function validateApiKey() {
    $api_key_file = '/var/local/poststack_api_key';

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

    // Check in request body
    $input = json_decode(file_get_contents('php://input'), true);
    if (isset($input['api_key'])) {
        return hash_equals($stored_key, $input['api_key']);
    }

    return false;
}

/**
 * Validate user input data
 */
function validateUserData($data) {
    $errors = [];

    if (empty($data['username']) || !is_string($data['username'])) {
        $errors[] = 'Username is required and must be a string';
    } elseif (strlen($data['username']) < 3 || strlen($data['username']) > 50) {
        $errors[] = 'Username must be between 3 and 50 characters';
    } elseif (!preg_match('/^[a-zA-Z0-9_-]+$/', $data['username'])) {
        $errors[] = 'Username can only contain letters, numbers, underscores, and hyphens';
    }

    if (empty($data['password']) || !is_string($data['password'])) {
        $errors[] = 'Password is required and must be a string';
    } elseif (strlen($data['password']) < 6) {
        $errors[] = 'Password must be at least 6 characters long';
    }

    if (isset($data['email']) && !empty($data['email'])) {
        if (!filter_var($data['email'], FILTER_VALIDATE_EMAIL)) {
            $errors[] = 'Invalid email format';
        }
    }

    if (isset($data['role']) && !in_array($data['role'], ['user', 'admin'], true)) {
        $errors[] = 'Role must be either "user" or "admin"';
    }

    return $errors;
}

try {
    // Validate API key
    if (!validateApiKey()) {
        http_response_code(401);
        echo json_encode(['error' => 'Invalid or missing API key']);
        exit();
    }

    // Parse request body
    $input = json_decode(file_get_contents('php://input'), true);

    if (json_last_error() !== JSON_ERROR_NONE) {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid JSON in request body']);
        exit();
    }

    // Validate input data
    $validation_errors = validateUserData($input);
    if (!empty($validation_errors)) {
        http_response_code(400);
        echo json_encode(['error' => 'Validation failed', 'details' => $validation_errors]);
        exit();
    }

    // Extract user data
    $username = trim($input['username']);
    $password = $input['password'];
    $email = isset($input['email']) ? trim($input['email']) : null;
    $role = isset($input['role']) ? $input['role'] : 'user';

    // Connect to database
    $dsn = sprintf(
        'pgsql:host=%s;port=%s;dbname=%s;options=--search_path=unified,public',
        $_SERVER['DB_HOST'] ?? 'localhost',
        $_SERVER['DB_PORT'] ?? '5432',
        $_SERVER['DB_NAME'] ?? 'unified_dev'
    );

    $pdo = new PDO($dsn, $_SERVER['DB_USER'] ?? 'poststack', $_SERVER['DB_PASSWORD'] ?? 'poststack_dev');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // Check if username already exists
    $stmt = $pdo->prepare('SELECT id FROM users WHERE username = ?');
    $stmt->execute([$username]);

    if ($stmt->fetch()) {
        http_response_code(409);
        echo json_encode(['error' => 'Username already exists']);
        exit();
    }

    // Check if email already exists (if provided)
    if ($email) {
        $stmt = $pdo->prepare('SELECT id FROM users WHERE email = ?');
        $stmt->execute([$email]);

        if ($stmt->fetch()) {
            http_response_code(409);
            echo json_encode(['error' => 'Email already exists']);
            exit();
        }
    }

    // Begin transaction for multi-table insert
    $pdo->beginTransaction();

    try {
        // Create new user in unified.users table
        $stmt = $pdo->prepare('
            INSERT INTO users (username, email, first_name, last_name, email_verified)
            VALUES (?, ?, ?, ?, true)
            RETURNING id, username, email, domain, created_at, is_active
        ');

        // Extract first/last name from username as fallback
        $first_name = ucfirst($username);
        $last_name = 'User';

        $stmt->execute([$username, $email, $first_name, $last_name]);
        $user = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$user) {
            throw new Exception('Failed to create user record');
        }

        $user_id = $user['id'];

        // Generate Apache MD5 hash for password (compatible with htpasswd -m)
        $apache_hash = crypt($password, '$1$' . substr(str_replace('+', '.', base64_encode(random_bytes(6))), 0, 8) . '$');

        // Insert password for Apache service
        $stmt = $pdo->prepare('
            INSERT INTO user_passwords (user_id, service, password_hash, hash_scheme)
            VALUES (?, ?, ?, ?)
        ');
        $stmt->execute([$user_id, 'apache', $apache_hash, 'CRYPT']);

        // Insert role for Apache service
        $stmt = $pdo->prepare('
            INSERT INTO user_roles (user_id, role_name, service)
            VALUES (?, ?, ?)
        ');
        $stmt->execute([$user_id, $role, 'apache']);

        // If creating an admin, also add dovecot access
        if ($role === 'admin') {
            // Add dovecot password (dovecot can use the same Apache hash)
            $stmt = $pdo->prepare('
                INSERT INTO user_passwords (user_id, service, password_hash, hash_scheme)
                VALUES (?, ?, ?, ?)
            ');
            $stmt->execute([$user_id, 'dovecot', $apache_hash, 'CRYPT']);

            // Add dovecot role
            $stmt = $pdo->prepare('
                INSERT INTO user_roles (user_id, role_name, service)
                VALUES (?, ?, ?)
            ');
            $stmt->execute([$user_id, 'admin', 'dovecot']);
        }

        // Commit transaction
        $pdo->commit();

    } catch (Exception $e) {
        $pdo->rollBack();
        throw $e;
    }

    // Log the creation
    error_log("User created successfully: username=$username, role=$role, id=" . $user['id']);

    // Return success response (don't include password)
    http_response_code(201);
    echo json_encode([
        'success' => true,
        'message' => 'User created successfully',
        'user' => [
            'id' => $user['id'],
            'username' => $user['username'],
            'email' => $user['email'],
            'domain' => $user['domain'],
            'role' => $role,
            'active' => $user['is_active'],
            'created_at' => $user['created_at']
        ]
    ]);

} catch (PDOException $e) {
    error_log("Database error in create_user.php: " . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Database error occurred']);
} catch (Exception $e) {
    error_log("General error in create_user.php: " . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Internal server error']);
}
?>
