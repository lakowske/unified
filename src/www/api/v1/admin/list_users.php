<?php
/**
 * User Listing API Endpoint
 *
 * Lists users from the unified.users table with API key authentication.
 * Used by unified service operations for user management.
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-API-Key');

// Handle preflight requests
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Only allow GET requests
if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed. Use GET.']);
    exit();
}

/**
 * Validate API key from request headers or query parameters
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

    // Check in query parameters (for GET requests)
    if (isset($_GET['api_key'])) {
        return hash_equals($stored_key, $_GET['api_key']);
    }

    return false;
}

/**
 * Parse query parameters for filtering and pagination
 */
function parseQueryParams() {
    $params = [
        'limit' => 50,  // Default limit
        'offset' => 0,  // Default offset
        'role' => null, // Filter by role
        'active' => null, // Filter by active status
        'search' => null, // Search in username/email
    ];

    // Parse limit (max 100)
    if (isset($_GET['limit'])) {
        $limit = intval($_GET['limit']);
        $params['limit'] = max(1, min(100, $limit));
    }

    // Parse offset
    if (isset($_GET['offset'])) {
        $params['offset'] = max(0, intval($_GET['offset']));
    }

    // Parse role filter
    if (isset($_GET['role']) && in_array($_GET['role'], ['user', 'admin'], true)) {
        $params['role'] = $_GET['role'];
    }

    // Parse active filter
    if (isset($_GET['active'])) {
        $active_value = strtolower($_GET['active']);
        if (in_array($active_value, ['true', '1', 'yes'], true)) {
            $params['active'] = true;
        } elseif (in_array($active_value, ['false', '0', 'no'], true)) {
            $params['active'] = false;
        }
    }

    // Parse search term
    if (isset($_GET['search']) && !empty(trim($_GET['search']))) {
        $params['search'] = trim($_GET['search']);
    }

    return $params;
}

try {
    // Validate API key
    if (!validateApiKey()) {
        http_response_code(401);
        echo json_encode(['error' => 'Invalid or missing API key']);
        exit();
    }

    // Parse query parameters
    $params = parseQueryParams();

    // Connect to database
    $dsn = sprintf(
        'pgsql:host=%s;port=%s;dbname=%s;options=--search_path=unified,public',
        $_SERVER['DB_HOST'] ?? 'localhost',
        $_SERVER['DB_PORT'] ?? '5432',
        $_SERVER['DB_NAME'] ?? 'unified_dev'
    );

    $pdo = new PDO($dsn, $_SERVER['DB_USER'] ?? 'unified', $_SERVER['DB_PASSWORD'] ?? 'unified_dev');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // Build WHERE clause
    $where_conditions = [];
    $where_params = [];

    if ($params['role']) {
        $where_conditions[] = 'ur.role_name = ?';
        $where_params[] = $params['role'];
    }

    if ($params['active'] !== null) {
        $where_conditions[] = 'u.is_active = ?';
        $where_params[] = $params['active'] ? 'true' : 'false';
    }

    if ($params['search']) {
        $where_conditions[] = '(u.username ILIKE ? OR u.email ILIKE ?)';
        $search_term = '%' . $params['search'] . '%';
        $where_params[] = $search_term;
        $where_params[] = $search_term;
    }

    $where_clause = !empty($where_conditions) ? 'WHERE ' . implode(' AND ', $where_conditions) : '';

    // Get total count (for pagination info)
    $count_sql = "
        SELECT COUNT(DISTINCT u.id)
        FROM users u
        LEFT JOIN user_roles ur ON u.id = ur.user_id AND ur.service = 'apache'
        $where_clause
    ";
    $count_stmt = $pdo->prepare($count_sql);
    $count_stmt->execute($where_params);
    $total_count = $count_stmt->fetchColumn();

    // Get users with pagination - join with roles for Apache service
    $sql = "
        SELECT DISTINCT u.id, u.username, u.email, u.domain,
               COALESCE(ur.role_name, 'user') as role,
               u.is_active as active, u.created_at, u.updated_at
        FROM users u
        LEFT JOIN user_roles ur ON u.id = ur.user_id AND ur.service = 'apache'
        $where_clause
        ORDER BY u.created_at DESC, u.username ASC
        LIMIT ? OFFSET ?
    ";

    $stmt = $pdo->prepare($sql);
    $stmt->execute(array_merge($where_params, [$params['limit'], $params['offset']]));
    $users = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // Calculate pagination info
    $has_more = ($params['offset'] + $params['limit']) < $total_count;
    $page_info = [
        'total_count' => intval($total_count),
        'returned_count' => count($users),
        'limit' => $params['limit'],
        'offset' => $params['offset'],
        'has_more' => $has_more
    ];

    // Log the request
    $filters_used = array_filter([
        $params['role'] ? "role={$params['role']}" : null,
        $params['active'] !== null ? "active=" . ($params['active'] ? 'true' : 'false') : null,
        $params['search'] ? "search={$params['search']}" : null,
    ]);
    $filters_str = empty($filters_used) ? 'none' : implode(', ', $filters_used);
    error_log("Users listed: total_count=$total_count, returned=" . count($users) . ", filters=[$filters_str]");

    // Return success response
    http_response_code(200);
    echo json_encode([
        'success' => true,
        'users' => $users,
        'pagination' => $page_info,
        'filters' => [
            'role' => $params['role'],
            'active' => $params['active'],
            'search' => $params['search']
        ]
    ]);

} catch (PDOException $e) {
    error_log("Database error in list_users.php: " . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Database error occurred']);
} catch (Exception $e) {
    error_log("General error in list_users.php: " . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Internal server error']);
}
?>
