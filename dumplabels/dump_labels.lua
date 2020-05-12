--saved_require = require

local cjson = (require "cjson").new()

local mod_dump_path = os.getenv("MOD_DUMP_PATH")
local cur_dir = string.gsub(arg[0], "/[^/]*$", "/")
local lualib_path = os.getenv("SCRIBUNTO_LUALIB") or (cur_dir .. "Scribunto/includes/engines/LuaCommon/lualib")
local lualib_ustring_path = lualib_path .. "/ustring"
package.path =
   package.path .. ";" .. lualib_path .. "/?.lua;" ..
   lualib_ustring_path .. "/?.lua"

local function lualib_require(mod)
  local path = lualib_path .. "/mw." .. mod .. ".lua"
  local f = assert(loadfile(path))
  return f()
end

local function starts_with(str, start)
   return str:sub(1, #start) == start
end

local function do_mod(mod)
  local esc_mod = string.gsub(mod, "/", "%%2F")
  local path = mod_dump_path .. "/" .. esc_mod
  local f = assert(loadfile(path))
  setfenv(f, sandbox)
  return f()
end

function mod_require(mod)
  if (starts_with(mod, "Module:")) then
    return do_mod(mod)
  else 
    error(string.format("Attempted to load non 'Module:' module: %s", mod))
    -- return saved_require(mod)
  end
end

sandbox = {
  mw = {
    loadData = mod_require,
    ustring = lualib_require("ustring")
  },
  require = mod_require,
  print = print,
  type = type,
  pairs = pairs,
  ipairs = ipairs,
  string = string,
  table = table,
  _prev = _G
}

function dump(o)
   if type(o) == 'table' then
      local s = '{ '
      for k,v in pairs(o) do
         if type(k) ~= 'number' then k = '"'..k..'"' end
         s = s .. '['..k..'] = ' .. dump(v) .. ','
      end
      return s .. '} '
   else
      return tostring(o)
   end
end

print(cjson.encode(do_mod("Module:labels/data")))
--print(dump(do_mod("Module:labels/data")))
