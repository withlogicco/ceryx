local exports = {}

function starts_with(subject, substring)
    return subject:sub(1, #substring) == substring
 end
 
 function ends_with(subject, substring)
    return subject:sub(-#substring) == substring
 end
 
 function starts_with_protocol(target)
     return starts_with(target, "http://") or starts_with(target, "https://")
 end
 
 function has_trailing_slash(target)
     return ends_with(target, "/")
 end
 
 function exports.ensure_protocol(target)
     if not starts_with_protocol(target) then
         return "http://" .. target
     end
 
     return target
 end
 
 function exports.ensure_no_trailing_slash(target)
     if has_trailing_slash(target) then
         return target:sub(1, -2)
     end
 
     return target
 end

 return exports