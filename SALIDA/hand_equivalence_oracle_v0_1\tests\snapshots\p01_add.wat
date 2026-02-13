(module
  (memory (export "memory") 1) ;; reserved (unused in pure subset)

  (func $add (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.add
    return
    i32.const 0
    return
  )
  (export "add" (func $add))

)
