#!/usr/bin/env php
<?php

use App\Ship;

require_once __DIR__ . '/../src/Ship.php';

$ship = new Ship();
$ship->land('Home');
