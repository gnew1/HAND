(module
  (memory (export "memory") 1) ;; reserved (unused in pure subset)

  (func $inc (param $a i32) (result i32)
    local.get $a
    i32.const 1
    i32.add
    return
    i32.const 0
    return
  )
  (export "inc" (func $inc))

  (func $twice (param $a i32) (result i32)
    local.get $a
    call $inc
    call $inc
    return
    i32.const 0
    return
  )
  (export "twice" (func $twice))

)
