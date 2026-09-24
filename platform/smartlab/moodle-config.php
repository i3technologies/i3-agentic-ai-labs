<?php  // Moodle configuration file

unset($CFG);
global $CFG;
$CFG = new stdClass();

$CFG->dbtype    = 'pgsql';
$CFG->dblibrary = 'native';
$CFG->dbhost    = 'i3-postgres-ha.i3-data.svc';
$CFG->dbname    = 'edbridge_db';
$CFG->dbuser    = 'edbridge';
$CFG->dbpass    = 'REDACTED-edbridge-db';
$CFG->prefix    = 'mdl_';
$CFG->dboptions = array (
  'dbpersist' => 0,
  'dbport' => 5432,
  'dbsocket' => '',
);

$CFG->wwwroot   = 'https://moodle.i3technologies.co.ke';
$CFG->dataroot  = '/var/www/moodledata';
$CFG->admin     = 'admin';

$CFG->directorypermissions = 02777;

// Reverse proxy / SSL termination settings (OpenShift edge router)
$CFG->sslproxy       = true;   // SSL terminated at OpenShift edge router
$CFG->reverseproxy   = false;

require_once(__DIR__ . '/lib/setup.php');

// There is no php closing tag in this file,
// it is intentional because it prevents trailing whitespace problems!
