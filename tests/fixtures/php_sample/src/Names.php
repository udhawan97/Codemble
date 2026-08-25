<?php

namespace Vendor {
    class RootThing {}
}

namespace Vendor\Pack {
    class Thing { public static function run(): void {} }
    class Other { public static function go(): void {} }
}

namespace App {
    use Vendor\Pack\{Thing, Other as Elsewhere};

    class LocalClass {}
    function local(): void {}

    function voyage(): void
    {
        new \Vendor\RootThing();
        new namespace\LocalClass();
        namespace\local();
        Thing::run();
        Elsewhere::go();
    }
}
