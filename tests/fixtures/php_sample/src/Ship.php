<?php

namespace App;

use App\Navigator;

require_once __DIR__ . '/Navigator.php';

#[Attribute]
final class Ship
{
    public function land(string $world): array|null
    {
        $route = Navigator::plot(world: $world);
        return $this->dock($route)?->manifest();
    }

    private function dock(array $route): ?object
    {
        return match (count($route)) {
            0 => null,
            default => (object) ['route' => $route],
        };
    }
}
