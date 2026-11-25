"""PG-CKPT-02: one atomic Redis projection update with exact decimal ordering."""

OFFER = r"""
local fresh = ARGV[1]
if redis.call('STRLEN', KEYS[1]) > 8192 then return 'INVALID' end
local prior = redis.call('GET', KEYS[1])
if not prior then redis.call('SET', KEYS[1], fresh, 'EX', ARGV[2]); return 'APPLIED' end
local ok, old = pcall(cjson.decode, prior)
local next = cjson.decode(fresh)
local function decimal(x)
 if type(x) ~= 'string' or not string.match(x, '^%d+$') then return false end
 if #x>1 and string.sub(x,1,1)=='0' then return false end
 return #x<19 or (#x==19 and x<='9223372036854775807')
end
local function cmp(a,b)
 if #a~=#b then return #a<#b and -1 or 1 end
 if a==b then return 0 end
 return a<b and -1 or 1
end
if not ok or type(old)~='table' or not decimal(old.epoch) or not decimal(old.sequence) then return 'INVALID' end
if old.db_role~=next.db_role or old.stream_id~=next.stream_id then return 'INVALID' end
local epoch = cmp(old.epoch,next.epoch)
local seq = cmp(old.sequence,next.sequence)
if epoch>0 or (epoch==0 and seq>0) then return 'STALE' end
if epoch==0 and seq==0 then
 if prior==fresh then return 'IDENTICAL' end
 return 'CONFLICT'
end
redis.call('SET',KEYS[1],fresh,'EX',ARGV[2]); return 'APPLIED'
"""

READ = (
    "if redis.call('STRLEN',KEYS[1])>8192 then return false end; return redis.call('GET',KEYS[1])"
)
