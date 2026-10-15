# What the patch changes

Generated from [patch.py](../patch.py) by `tools/verify_patchers.py --write-doc` - do not edit.
The player patchers ([player/](../player/)) write exactly these bytes; `tools/verify_patchers.py`
re-assembles them from the source below and checks that, on every push (GitHub Actions).

The patch is for `empire.retail.dll` of the Steam Windows build (SHA-256 `022fae2e2da92b59b8b1b8ee52887003c624e3c8eca060b209f5d792a7f874f5`).
It changes 478 bytes in 15 places and nothing else:

| What | File offset |
|---|---|
| `.text` section header, VirtualSize: 0x159fc3e -> 0x159fe00, so the section's unused tail (zero bytes already in the file) becomes part of the code | `0x260` |
| Hook 1, unit-ability builder: a 6-byte branch now jumps to routine 1 | `0x19da43` |
| Hook 2, same loop: a 7-byte instruction pair now jumps to routine 2 | `0x19daf2` |
| Stat hook, land unit stats builder: a `call` now goes to a stat routine (`charge_bonus`, unit_record id 0x1b) | `0x151a20` |
| Stat hook, land unit stats builder: a `call` now goes to a stat routine (`reload`, unit_record id 0x14) | `0x151b0d` |
| Stat hook, land unit stats builder: a `call` now goes to a stat routine (`range_mod`, unit_record id 0x17) | `0x151c14` |
| Stat hook, land unit stats builder: a `call` now goes to a stat routine (`mod_land_movement_battle`, unit_record id 0x19) | `0x151c46` |
| Stat hook, land unit stats builder: a `call` now goes to a stat routine (`ammo_mod`, unit_record id 0x18) | `0x151c78` |
| Range routine, in unused int3 padding: adds the class + unit_record range bonus to the unit's additive range field (the vanilla code multiplied it, and it starts at 0) | `0xb4f20` |
| Drop-in off: the campaign's drop-in battles flag is always computed as off (the preference defaults to on) | `0x11854bd` |
| Drop-in off: the drop-in flag's setter always stores off | `0x1188401` |
| Drop-in off: the handler for a drop-in invitation ("Drop-in battle available") returns before telling the UI | `0x1153316` |
| Drop-in off: starting to host a drop-in battle (CampaignUI.PlayDropInBattle) returns 0, not started | `0x11236b0` |
| Parser hook: the unit_record bonus-name parser's not-found exit jumps to the parser extension | `0xbd315d` |
| New code in the unused tail: the routines below and the signature `VU_ABILITY_PATCH 4` | `0x15a0040` |

What it does, in words:

* **Abilities.** When the game builds a unit's list of battle abilities, an ability that needs
  unlocking and isn't unlocked normally gets skipped. Hook 1 sends that case to routine 1, which only
  acts on the mod's own "clone" ability records (keys `vuNN_...`): it reads the unit type's
  `general_aoe_mod` bonus, and if bit NN is set (and any research the real ability needs is done) it
  adds the real ability instead of skipping. Hook 2 restores the loop's position afterwards.
* **Stats.** The game adds clan bonuses to a land unit's charge, reload, range, speed and ammunition
  only per unit class or category (and its class range bonus never worked: it multiplied a field that
  starts at 0). Each stat hook keeps that lookup and also adds the same kind of
  bonus for the unit's own type (unit_record). The parser extension lets effects name these bonuses
  for a unit type (see the table below).
* **Drop-in battles off.** A drop-in battle is an online battle against another player, so with a
  modified game file it could get the player's Steam account banned (Valve Anti-Cheat). Invitations
  to join someone else's battle are never shown, and battles are never offered to other players
  (the game's drop-in setting is treated as off; hosting is refused as a backstop).

The stat bonuses:

| unit_record bonus | adds |
|---|---|
| `charge_bonus` | charge bonus, added to the unit class's |
| `reload` | reload skill %, added to the unit class's |
| `range_mod` | missile range, added to the unit's range bonus (the field the Increased Range ability raises) |
| `mod_land_movement_battle` | battle speed %, added to the unit category's |
| `ammo_mod` | ammunition %, added to the unit class's |

The new code calls only the game's own functions (its bonus lookups, its research check and the name
comparison the parser already uses), allocates nothing, and touches no files, network or other programs.
It uses no absolute addresses, so it works wherever Windows loads the DLL.

## Hooks

```
Original at 0x1019e643 (file offset 0x19da43):
1019e643  0f84a9000000     je 0x1019e6f2
Patched:
1019e643  e9f8254001       jmp 0x115a0c40
1019e648  90               nop

Original at 0x1019e6f2 (file offset 0x19daf2):
1019e6f2  8b542424         mov edx, dword ptr [esp + 0x24]
1019e6f6  83c304           add ebx, 4
Patched:
1019e6f2  e90d264001       jmp 0x115a0d04
1019e6f7  90               nop
1019e6f8  90               nop

Original at 0x10152620 (file offset 0x151a20):
10152620  e81bcea700       call 0x10bcf440
Patched:
10152620  e8f7e64401       call 0x115a0d1c

Original at 0x1015270d (file offset 0x151b0d):
1015270d  e82ecda700       call 0x10bcf440
Patched:
1015270d  e80ae64401       call 0x115a0d1c

Original at 0x10152814 (file offset 0x151c14):
10152814  e8a7caa700       call 0x10bcf2c0
Patched:
10152814  e80733f6ff       call 0x100b5b20

Original at 0x10152846 (file offset 0x151c46):
10152846  e855caa700       call 0x10bcf2a0
Patched:
10152846  e82de54401       call 0x115a0d78

Original at 0x10152878 (file offset 0x151c78):
10152878  e843caa700       call 0x10bcf2c0
Patched:
10152878  e8ffe44401       call 0x115a0d7c

Original at 0x100b5b20 (file offset 0xb4f20):
100b5b20  cc               int3
100b5b21  cc               int3
100b5b22  cc               int3
100b5b23  cc               int3
100b5b24  cc               int3
100b5b25  cc               int3
100b5b26  cc               int3
100b5b27  cc               int3
100b5b28  cc               int3
100b5b29  cc               int3
100b5b2a  cc               int3
100b5b2b  cc               int3
100b5b2c  cc               int3
100b5b2d  cc               int3
100b5b2e  cc               int3
100b5b2f  cc               int3
100b5b30  cc               int3
100b5b31  cc               int3
100b5b32  cc               int3
100b5b33  cc               int3
100b5b34  cc               int3
100b5b35  cc               int3
100b5b36  cc               int3
100b5b37  cc               int3
100b5b38  cc               int3
100b5b39  cc               int3
100b5b3a  cc               int3
100b5b3b  cc               int3
100b5b3c  cc               int3
100b5b3d  cc               int3
100b5b3e  cc               int3
100b5b3f  cc               int3
Patched:
100b5b20  ff742408         push dword ptr [esp + 8]
100b5b24  ff742408         push dword ptr [esp + 8]
100b5b28  e84fb24e01       call 0x115a0d7c
100b5b2d  d88424c4000000   fadd dword ptr [esp + 0xc4]
100b5b34  d99c24c4000000   fstp dword ptr [esp + 0xc4]
100b5b3b  d9ee             fldz
100b5b3d  c20800           ret 8

Original at 0x111860bd (file offset 0x11854bd):
111860bd  b001             mov al, 1
Patched:
111860bd  30c0             xor al, al

Original at 0x11189001 (file offset 0x1188401):
11189001  8a5c2408         mov bl, byte ptr [esp + 8]
Patched:
11189001  31db             xor ebx, ebx
11189003  90               nop
11189004  90               nop

Original at 0x11153f16 (file offset 0x1153316):
11153f16  83ec24           sub esp, 0x24
11153f19  6a00             push 0
Patched:
11153f16  31c0             xor eax, eax
11153f18  c20400           ret 4

Original at 0x111242b0 (file offset 0x11236b0):
111242b0  56               push esi
111242b1  8bf1             mov esi, ecx
Patched:
111242b0  31c0             xor eax, eax
111242b2  c20800           ret 8

Original at 0x10bd3d5d (file offset 0xbd315d):
10bd3d5d  5f               pop edi
10bd3d5e  b80d000000       mov eax, 0xd
10bd3d63  5e               pop esi
10bd3d64  c3               ret
Patched:
10bd3d5d  e942d09c00       jmp 0x115a0da4
10bd3d62  90               nop
10bd3d63  90               nop
10bd3d64  90               nop
```

## Routine 1 (abilities) (`0x115a0c40`)

```
115a0c40  85c0             test eax, eax
115a0c42  0f85ad000000     jne 0x115a0cf5
115a0c48  8b571c           mov edx, dword ptr [edi + 0x1c]
115a0c4b  85d2             test edx, edx
115a0c4d  0f84aa000000     je 0x115a0cfd
115a0c53  833f05           cmp dword ptr [edi], 5
115a0c56  0f82a1000000     jb 0x115a0cfd
115a0c5c  8b4f08           mov ecx, dword ptr [edi + 8]
115a0c5f  66833976         cmp word ptr [ecx], 0x76
115a0c63  0f8594000000     jne 0x115a0cfd
115a0c69  6683790275       cmp word ptr [ecx + 2], 0x75
115a0c6e  0f8589000000     jne 0x115a0cfd
115a0c74  668379085f       cmp word ptr [ecx + 8], 0x5f
115a0c79  7407             je 0x115a0c82
115a0c7b  6683790866       cmp word ptr [ecx + 8], 0x66
115a0c80  757b             jne 0x115a0cfd
115a0c82  0fb74104         movzx eax, word ptr [ecx + 4]
115a0c86  83e830           sub eax, 0x30
115a0c89  83f809           cmp eax, 9
115a0c8c  776f             ja 0x115a0cfd
115a0c8e  6bc00a           imul eax, eax, 0xa
115a0c91  0fb74906         movzx ecx, word ptr [ecx + 6]
115a0c95  83e930           sub ecx, 0x30
115a0c98  83f909           cmp ecx, 9
115a0c9b  7760             ja 0x115a0cfd
115a0c9d  01c8             add eax, ecx
115a0c9f  83f818           cmp eax, 0x18
115a0ca2  7359             jae 0x115a0cfd
115a0ca4  52               push edx
115a0ca5  50               push eax
115a0ca6  8b4c2430         mov ecx, dword ptr [esp + 0x30]
115a0caa  8b44242c         mov eax, dword ptr [esp + 0x2c]
115a0cae  2dfc000000       sub eax, 0xfc
115a0cb3  6a09             push 9
115a0cb5  6a00             push 0
115a0cb7  50               push eax
115a0cb8  6a10             push 0x10
115a0cba  e8215263ff       call 0x10bd5ee0
115a0cbf  59               pop ecx
115a0cc0  0fa3c8           bt eax, ecx
115a0cc3  7335             jae 0x115a0cfa
115a0cc5  8b4708           mov eax, dword ptr [edi + 8]
115a0cc8  6683780866       cmp word ptr [eax + 8], 0x66
115a0ccd  7419             je 0x115a0ce8
115a0ccf  8b0424           mov eax, dword ptr [esp]
115a0cd2  80782000         cmp byte ptr [eax + 0x20], 0
115a0cd6  7410             je 0x115a0ce8
115a0cd8  8b4c242c         mov ecx, dword ptr [esp + 0x2c]
115a0cdc  6a00             push 0
115a0cde  50               push eax
115a0cdf  e8fce662ff       call 0x10bcf3e0
115a0ce4  85c0             test eax, eax
115a0ce6  7412             je 0x115a0cfa
115a0ce8  58               pop eax
115a0ce9  89442410         mov dword ptr [esp + 0x10], eax
115a0ced  895c2414         mov dword ptr [esp + 0x14], ebx
115a0cf1  8d5c2410         lea ebx, [esp + 0x10]
115a0cf5  e94fd9bffe       jmp 0x1019e649
115a0cfa  83c404           add esp, 4
115a0cfd  e9f0d9bffe       jmp 0x1019e6f2
```

Source (keystone syntax, from patch.py):

```
test eax, eax
    jnz grant
    mov edx, dword ptr [edi + 0x1c]
    test edx, edx
    jz skip
    cmp dword ptr [edi + 0x0], 5
    jb skip
    mov ecx, dword ptr [edi + 0x8]
    cmp word ptr [ecx], 0x76
    jne skip
    cmp word ptr [ecx + 2], 0x75
    jne skip
    cmp word ptr [ecx + 8], 0x5f
    je key_ok
    cmp word ptr [ecx + 8], 0x66
    jne skip
key_ok:
    movzx eax, word ptr [ecx + 4]
    sub eax, 0x30
    cmp eax, 9
    ja skip
    imul eax, eax, 10
    movzx ecx, word ptr [ecx + 6]
    sub ecx, 0x30
    cmp ecx, 9
    ja skip
    add eax, ecx
    cmp eax, 24
    jae skip
    push edx
    push eax
    mov ecx, dword ptr [esp + 0x30]
    mov eax, dword ptr [esp + 0x2c]
    sub eax, 0xfc
    push 9
    push 0
    push eax
    push 0x10
    call 0x10bd5ee0
    pop ecx
    bt eax, ecx
    jnc skip1
    mov eax, dword ptr [edi + 0x8]
    cmp word ptr [eax + 8], 0x66
    je substitute
    mov eax, dword ptr [esp]
    cmp byte ptr [eax + 0x20], 0
    je substitute
    mov ecx, dword ptr [esp + 0x2c]
    push 0
    push eax
    call 0x10bcf3e0
    test eax, eax
    jz skip1
substitute:
    pop eax
    mov dword ptr [esp + 0x10], eax
    mov dword ptr [esp + 0x14], ebx
    lea ebx, [esp + 0x10]
grant:
    jmp 0x1019e649
skip1:
    add esp, 4
skip:
    jmp 0x1019e6f2
```

## Routine 2 (abilities) (`0x115a0d04`)

```
115a0d04  8d442410         lea eax, [esp + 0x10]
115a0d08  39c3             cmp ebx, eax
115a0d0a  7504             jne 0x115a0d10
115a0d0c  8b5c2414         mov ebx, dword ptr [esp + 0x14]
115a0d10  8b542424         mov edx, dword ptr [esp + 0x24]
115a0d14  83c304           add ebx, 4
115a0d17  e9ddd9bffe       jmp 0x1019e6f9
```

Source (keystone syntax, from patch.py):

```
lea eax, [esp + 0x10]
    cmp ebx, eax
    jne advance
    mov ebx, dword ptr [esp + 0x14]
advance:
    mov edx, dword ptr [esp + 0x24]
    add ebx, 4
    jmp 0x1019e6f9
```

## Stat routines (`0x115a0d1c`)

```
115a0d1c  51               push ecx
115a0d1d  ff74240c         push dword ptr [esp + 0xc]
115a0d21  6a00             push 0
115a0d23  ff742410         push dword ptr [esp + 0x10]
115a0d27  6a0d             push 0xd
115a0d29  e8b25163ff       call 0x10bd5ee0
115a0d2e  59               pop ecx
115a0d2f  50               push eax
115a0d30  8b44240c         mov eax, dword ptr [esp + 0xc]
115a0d34  83c010           add eax, 0x10
115a0d37  50               push eax
115a0d38  6a00             push 0
115a0d3a  56               push esi
115a0d3b  6a10             push 0x10
115a0d3d  e89e5163ff       call 0x10bd5ee0
115a0d42  5a               pop edx
115a0d43  01d0             add eax, edx
115a0d45  c20800           ret 8
115a0d48  58               pop eax
115a0d49  51               push ecx
115a0d4a  ff74240c         push dword ptr [esp + 0xc]
115a0d4e  6a00             push 0
115a0d50  ff742410         push dword ptr [esp + 0x10]
115a0d54  50               push eax
115a0d55  e8165163ff       call 0x10bd5e70
115a0d5a  59               pop ecx
115a0d5b  50               push eax
115a0d5c  d91c24           fstp dword ptr [esp]
115a0d5f  8b44240c         mov eax, dword ptr [esp + 0xc]
115a0d63  83c010           add eax, 0x10
115a0d66  50               push eax
115a0d67  6a00             push 0
115a0d69  56               push esi
115a0d6a  6a10             push 0x10
115a0d6c  e8ff5063ff       call 0x10bd5e70
115a0d71  d80424           fadd dword ptr [esp]
115a0d74  58               pop eax
115a0d75  c20800           ret 8
115a0d78  6a0e             push 0xe
115a0d7a  ebcc             jmp 0x115a0d48
115a0d7c  6a0d             push 0xd
115a0d7e  ebc8             jmp 0x115a0d48
```

Source (keystone syntax, from patch.py):

```
stat_int:
    push ecx
    push dword ptr [esp + 0xc]
    push 0
    push dword ptr [esp + 0x10]
    push 0xd
    call 0x10bd5ee0
    pop ecx
    push eax
    mov eax, dword ptr [esp + 0xc]
    add eax, 0x10
    push eax
    push 0
    push esi
    push 0x10
    call 0x10bd5ee0
    pop edx
    add eax, edx
    ret 8
stat_f:
    pop eax
    push ecx
    push dword ptr [esp + 0xc]
    push 0
    push dword ptr [esp + 0x10]
    push eax
    call 0x10bd5e70
    pop ecx
    push eax
    fstp dword ptr [esp]
    mov eax, dword ptr [esp + 0xc]
    add eax, 0x10
    push eax
    push 0
    push esi
    push 0x10
    call 0x10bd5e70
    fadd dword ptr [esp]
    pop eax
    ret 8
stat_category_f:
    push 0xe
    jmp stat_f
stat_class_f:
    push 0xd
    jmp stat_f
```

## Parser extension (`0x115a0da4`)

```
115a0da4  e800000000       call 0x115a0da9
115a0da9  5e               pop esi
115a0daa  83c62b           add esi, 0x2b
115a0dad  8b06             mov eax, dword ptr [esi]
115a0daf  85c0             test eax, eax
115a0db1  7419             je 0x115a0dcc
115a0db3  01f0             add eax, esi
115a0db5  50               push eax
115a0db6  89f9             mov ecx, edi
115a0db8  e813d5b4fe       call 0x100ee2d0
115a0dbd  84c0             test al, al
115a0dbf  7505             jne 0x115a0dc6
115a0dc1  83c605           add esi, 5
115a0dc4  ebe7             jmp 0x115a0dad
115a0dc6  0fb64604         movzx eax, byte ptr [esi + 4]
115a0dca  eb05             jmp 0x115a0dd1
115a0dcc  b80d000000       mov eax, 0xd
115a0dd1  5f               pop edi
115a0dd2  5e               pop esi
115a0dd3  c3               ret

Name table (int32 name VA minus entry VA, then the id byte; 0 ends it):
115a0dd4  84dc0a001b  charge_bonus -> 0x1b
115a0dd9  fbdc0a0014  reload -> 0x14
115a0dde  0edd0a0017  range_mod -> 0x17
115a0de3  85dc0a0019  mod_land_movement_battle -> 0x19
115a0de8  b0cf0a0018  ammo_mod -> 0x18
```

Source (keystone syntax, from patch.py):

```
call here
here:
    pop esi
    add esi, TABLE_DELTA
next_name:
    mov eax, dword ptr [esi]
    test eax, eax
    jz not_found
    add eax, esi
    push eax
    mov ecx, edi
    call 0x100ee2d0
    test al, al
    jnz found
    add esi, 5
    jmp next_name
found:
    movzx eax, byte ptr [esi + 4]
    jmp done
not_found:
    mov eax, 0xd
done:
    pop edi
    pop esi
    ret
```
