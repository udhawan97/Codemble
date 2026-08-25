#!/usr/bin/env ruby

require_relative "../lib/atlas"

if $PROGRAM_NAME == __FILE__
  Atlas::Ship.launch("Home")
end
