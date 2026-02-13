(module
  (memory (export "memory") 1) ;; reserved (unused in pure subset)

  (func $max (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.ge_s
    if
      local.get $a
      return
    else
      local.get $b
      return
    end
    i32.const 0
    return
  )
  (export "max" (func $max))

)
