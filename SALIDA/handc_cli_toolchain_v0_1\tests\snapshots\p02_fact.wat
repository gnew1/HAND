(module
  (memory (export "memory") 1) ;; reserved (unused in pure subset)

  (func $fact (param $n i32) (result i32)
    (local $acc i32)
    (local $i i32)
    i32.const 1
    local.set $acc
    i32.const 1
    local.set $i
    block $exit
      loop $loop
        local.get $i
        local.get $n
        i32.le_s
        i32.eqz
        br_if $exit
        local.get $acc
        local.get $i
        i32.mul
        local.set $acc
        local.get $i
        i32.const 1
        i32.add
        local.set $i
        br $loop
      end
    end
    local.get $acc
    return
    i32.const 0
    return
  )
  (export "fact" (func $fact))

)
