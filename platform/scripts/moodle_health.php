<?php
define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
echo "CONFIG_OK wwwroot=" . $CFG->wwwroot . PHP_EOL;
echo "DB host=" . $CFG->dbhost . PHP_EOL;
echo "DB name=" . $CFG->dbname . PHP_EOL;

// Check moodle is installed (has site table)
try {
    $count = $DB->count_records('course');
    echo "COURSES=" . $count . PHP_EOL;
    echo "MOODLE_HEALTHY=true" . PHP_EOL;
} catch (Exception $e) {
    echo "DB_ERROR: " . $e->getMessage() . PHP_EOL;
}
