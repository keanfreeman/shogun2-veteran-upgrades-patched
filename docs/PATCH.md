# What the patch changes

Generated from [patch.py](../patch.py) by `tools/verify_patchers.py --write-doc` - do not edit.
The player patchers ([player/](../player/)) write exactly these bytes; `tools/verify_patchers.py`
re-assembles them from the source below and checks that, on every push (GitHub Actions).

The patch is for `empire.retail.dll` of the Steam Windows build (SHA-256 `022fae2e2da92b59b8b1b8ee52887003c624e3c8eca060b209f5d792a7f874f5`).
It changes 348 bytes in four places and nothing else:

| Where | File offset | What |
|---|---|---|
| `.text` section header, VirtualSize | `0x260` | 0x159fc3e -> 0x159fe00: the section's unused tail (zero bytes already in the file) becomes part of the code |
| Hook 1, in the unit-ability builder | `0x19da43` | a 6-byte branch now jumps to routine 1 |
| Hook 2, same loop | `0x19daf2` | a 7-byte instruction pair now jumps to routine 2 |
| New code in the unused tail | `0x15a0040` | routine 1, routine 2 and the signature `VU_ABILITY_PATCH 3` |

What it does, in words: when the game builds a unit's list of battle abilities, an ability that needs
unlocking and isn't unlocked normally gets skipped. Hook 1 sends that case to routine 1, which only acts
on the mod's own "clone" ability records (keys `vuNN_...`): it reads the unit type's `general_aoe_mod`
bonus, and if bit NN is set (and any research the real ability needs is done) it adds the real ability
instead of skipping. Hook 2 restores the loop's position afterwards. The new code calls only two of the
game's own functions (its bonus lookup and its research check), allocates nothing, and touches no files,
network or other programs.

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
1019e6f2  e929264001       jmp 0x115a0d20
1019e6f7  90               nop
1019e6f8  90               nop
```

## Routine 1 (`0x115a0c40`)

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

## Routine 2 (`0x115a0d20`)

```
115a0d20  8d442410         lea eax, [esp + 0x10]
115a0d24  39c3             cmp ebx, eax
115a0d26  7504             jne 0x115a0d2c
115a0d28  8b5c2414         mov ebx, dword ptr [esp + 0x14]
115a0d2c  8b542424         mov edx, dword ptr [esp + 0x24]
115a0d30  83c304           add ebx, 4
115a0d33  e9c1d9bffe       jmp 0x1019e6f9
```

Source:

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
