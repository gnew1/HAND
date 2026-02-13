(module
  (memory (export "memory") 1) ;; reserved (unused in pure subset)

  (func $is_zero (param $a i32) (result i32)
    local.get $a
    i32.const 0
    i32.eq
    return
    i32.const 0
    return
  )
  (export "is_zero" (func $is_zero))

)
