require_relative "atlas/navigation"

module Atlas
  class Ship
    def self.launch(target)
      prime
      route = Atlas::Navigator.plot(target)
      route&.each { |stop| puts("Landing at #{stop}") }
    end

    class << self
      def prime
        true
      end
    end

    def land(world)
      { world: world, status: :charted }
    rescue StandardError
      { world: world, status: :unknown }
    end
  end
end
