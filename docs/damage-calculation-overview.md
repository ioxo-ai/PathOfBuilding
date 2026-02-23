# Path of Building 데미지 계산식 정리

## 목차

1. [전체 계산 흐름](#1-전체-계산-흐름)
2. [핵심 모듈 구조](#2-핵심-모듈-구조)
3. [기본 데미지 공식 (Hit Damage)](#3-기본-데미지-공식-hit-damage)
4. [데미지 타입과 플래그 시스템](#4-데미지-타입과-플래그-시스템)
5. [데미지 전환 (Conversion) 시스템](#5-데미지-전환-conversion-시스템)
6. [크리티컬 스트라이크 계산](#6-크리티컬-스트라이크-계산)
7. [명중률 (Hit Chance) 계산](#7-명중률-hit-chance-계산)
8. [적 저항 및 데미지 경감](#8-적-저항-및-데미지-경감)
9. [DoT (Damage over Time) 계산](#9-dot-damage-over-time-계산)
10. [최종 DPS 산출](#10-최종-dps-산출)

---

## 1. 전체 계산 흐름

**엔트리 포인트:** `Calcs.lua:416` - `calcs.buildOutput(build, mode)`

```
calcs.buildOutput()
  ├── calcs.initEnv()        -- 환경 초기화 (모디파이어 DB 세팅)
  ├── calcs.perform()        -- 메인 계산 수행
  │     ├── calcs.offence()  -- 공격 계산 (CalcOffence.lua)
  │     └── calcs.defence()  -- 방어 계산 (CalcDefence.lua)
  └── calcs.calcFullDPS()    -- 전체 스킬 DPS 합산
```

**계산 순서:**
1. `CalcSetup.lua` — 환경 초기화, 모디파이어 데이터베이스 구축
2. `CalcActiveSkill.lua` — 액티브 스킬 설정 및 스킬 플래그 초기화
3. `CalcPerform.lua` — 공격/방어 계산 오케스트레이션
4. `CalcOffence.lua` — 히트 데미지, 크리, DoT 등 공격 전체 계산
5. `CalcDefence.lua` — 방어구, 저항, 데미지 감소 계산
6. `CalcTriggers.lua` — 트리거 스킬 처리
7. `CalcMirages.lua` — 미라지 관련 계산

---

## 2. 핵심 모듈 구조

| 파일 | 역할 |
|------|------|
| `src/Modules/Calcs.lua` | 계산 시스템 관리자. 모든 모듈 로드 및 `buildOutput()` 엔트리 포인트 |
| `src/Modules/CalcSetup.lua` | 환경 초기화, 모디파이어 DB 세팅 |
| `src/Modules/CalcPerform.lua` | 공격/방어 계산 오케스트레이션 |
| `src/Modules/CalcActiveSkill.lua` | 액티브 스킬 구성 및 타입/플래그 초기화 |
| `src/Modules/CalcOffence.lua` | **핵심 — 모든 공격 데미지 계산** |
| `src/Modules/CalcDefence.lua` | 방어 계산 (아머, 저항, 회피 등) |
| `src/Modules/CalcTriggers.lua` | 트리거 스킬 처리 |
| `src/Modules/CalcMirages.lua` | 미라지 (분신) 계산 |

---

## 3. 기본 데미지 공식 (Hit Damage)

**코드 위치:** `CalcOffence.lua:68-139` — `calcDamage()` 함수

### 3.1 베이스 데미지

```
baseMin = weapon[damageTypeMin] * baseMultiplier + addedMin * damageEffectiveness
baseMax = weapon[damageTypeMax] * baseMultiplier + addedMax * damageEffectiveness
```

- `baseMultiplier` — 스킬의 베이스 데미지 배율
- `damageEffectiveness` — 추가 데미지(Added Damage) 적용 비율

### 3.2 모디파이어 적용

```lua
inc  = 1 + skillModList:Sum("INC", cfg, ...) / 100    -- Increased/Reduced
more = skillModList:More(cfg, ...)                       -- More/Less
```

- **INC (Increased/Reduced):** 합산 후 곱셈 (additive → multiplicative)
- **MORE (More/Less):** 각각 개별 곱셈 (multiplicative)

### 3.3 최종 데미지 공식

```lua
damageMin = round(((baseMin * inc * more) * genericMoreMinDamage + addMin) * moreMinDamage)
damageMax = round(((baseMax * inc * more) * genericMoreMaxDamage + addMax) * moreMaxDamage)
```

**분해하면:**

```
최종 데미지 = ((베이스 × INC × MORE) × 일반 More_Min/Max + 전환으로 받은 추가 데미지) × 타입별 More_Min/Max
```

여기서:
- `genericMoreMinDamage` / `genericMoreMaxDamage` — 타입 무관 Min/Max 데미지 More 배율
- `moreMinDamage` / `moreMaxDamage` — 해당 타입 전용 Min/Max 데미지 More 배율
- `addMin` / `addMax` — 다른 타입에서 전환(Conversion/Gain)으로 유입된 데미지

---

## 4. 데미지 타입과 플래그 시스템

**코드 위치:** `CalcOffence.lua:30-44`

### 4.1 데미지 타입 순서 (전환 순서)

```lua
dmgTypeList = {"Physical", "Lightning", "Cold", "Fire", "Chaos"}
```

전환은 반드시 이 순서의 **오른쪽**으로만 가능:
```
Physical → Lightning → Cold → Fire → Chaos
    ↘          ↘         ↘      ↘
    Lightning   Cold      Fire    Chaos
    Cold        Fire      Chaos
    Fire        Chaos
    Chaos
```

### 4.2 데미지 플래그

```lua
Physical  = 0x01
Lightning = 0x02
Cold      = 0x04
Fire      = 0x08
Elemental = 0x0E  (Lightning | Cold | Fire)
Chaos     = 0x10
```

- 비트 OR 연산으로 복합 타입 플래그를 구성
- `Elemental`은 Lightning + Cold + Fire의 조합
- 모디파이어 검색 시 해당 플래그에 맞는 모든 관련 모디파이어를 수집

### 4.3 타입별 모디파이어 수집

```lua
-- CalcOffence.lua:52-62 - damageStatsForTypes 메타테이블
-- 예: Physical + Fire 플래그가 설정되면
modNames = {"Damage", "PhysicalDamage", "FireDamage"}
```

이렇게 수집된 모디파이어 이름들이 INC/MORE 계산에 사용됨.

---

## 5. 데미지 전환 (Conversion) 시스템

**코드 위치:** `CalcOffence.lua:1840-1883` (conversionTable 구축), `CalcOffence.lua:68-93` (재귀 적용)

### 5.1 전환 테이블 구조

각 데미지 타입마다 다음 구조의 테이블 생성:

```lua
conversionTable[damageType] = {
    conversion = { [targetType] = percent },  -- 전환 비율 (0~1)
    gain       = { [targetType] = percent },  -- 추가 획득 비율 (0~1)
    mult       = remainingMultiplier,          -- 전환 후 남은 비율 (1 - 총전환%)
    [targetType] = totalPercent               -- 전환 + 추가 합산 비율
}
```

### 5.2 전환 우선순위

1. **스킬 전환 (Skill Conversion):** 스킬 자체의 전환이 최우선
2. **글로벌 전환 (Global Conversion):** 아이템/패시브 등의 전환

**오버플로우 처리:**
- 스킬 전환만으로 100% 초과 시 → 스킬 전환을 비례 축소, 글로벌 전환 0으로
- 스킬 + 글로벌 합산이 100% 초과 시 → 글로벌 전환을 비례 축소

```lua
-- 스킬 전환 합계가 100% 초과
if skillTotal > 100 then
    factor = 100 / skillTotal
    -- 모든 스킬 전환을 factor로 축소
    -- 글로벌 전환 = 0

-- 스킬 + 글로벌 합산이 100% 초과
elseif globalTotal + skillTotal > 100 then
    factor = (100 - skillTotal) / globalTotal
    -- 글로벌 전환을 factor로 축소
end
```

### 5.3 재귀적 전환 계산

`calcDamage()` 함수 내에서 재귀적으로 전환 체인을 처리:

```lua
-- CalcOffence.lua:74-93
for _, otherType in ipairs(dmgTypeList) do
    if otherType == damageType then break end  -- 선행 타입만 처리

    local convMult = conversionTable[otherType][damageType]
    if convMult > 0 then
        -- 재귀 호출: 원본 타입의 데미지 계산
        local min, max = calcDamage(..., otherType, typeFlags, damageType)
        addMin = addMin + min * convMult
        addMax = addMax + max * convMult
    end
end
```

**예시: Physical → Fire 100% 전환**
1. `calcDamage(Fire)` 호출
2. Physical에서 Fire로의 전환을 감지
3. `calcDamage(Physical)` 재귀 호출 → Physical의 min/max 계산
4. Physical 결과에 전환 비율을 곱해 Fire 데미지에 추가
5. Fire 자체 베이스 데미지 + 전환 데미지 합산 후 Fire 모디파이어 적용

**핵심:** 전환된 데미지는 **원본 타입의 모디파이어**와 **목적 타입의 모디파이어** 모두의 영향을 받음 (double-dipping 방지를 위한 typeFlags 시스템).

---

## 6. 크리티컬 스트라이크 계산

**코드 위치:** `CalcOffence.lua:2826-3001`

### 6.1 크리티컬 확률

```lua
baseCrit = source.CritChance or 0  -- 스킬/무기의 기본 크리 확률
```

**최종 크리 확률:**
```
CritChance = baseCrit * (1 + INC_CritChance/100) * MORE_CritChance
```

- 최소 5%, 최대 100%로 클램핑
- 명중률(AccuracyHitChance)이 적용됨: `CritChance = CritChance * AccuracyHitChance / 100`

### 6.2 Lucky/Unlucky 크리

```lua
if critRolls ~= 0 then
    CritChance = (1 - (1 - CritChance/100) ^ (critRolls + 1)) * 100
end
```

- Lucky: 크리 판정을 여러 번 굴려서 하나라도 성공하면 크리
- Unlucky: 반대 방향으로 동작

### 6.3 크리티컬 배율 (Critical Multiplier)

```
CritMultiplier = 1.5 (기본) + INC_CritMultiplier/100
```

- PoE 기본 크리 배율: 150% (= 1.5x)
- "Increased Critical Damage" 모디파이어로 증가

### 6.4 유효 크리 배율 (CritEffect)

```lua
-- CalcOffence.lua:2995-3001
CritEffect = (1 - critChance%) + critChance% * CritMultiplier
```

이것이 최종 데미지에 곱해지는 유효 크리 배율:
- 크리 확률 50%, 크리 배율 2.0x인 경우:
  `CritEffect = 0.5 * 1.0 + 0.5 * 2.0 = 1.5`

### 6.5 Two-Pass 시스템

```lua
-- CalcOffence.lua:3100
for pass = 1, 2 do
    -- Pass 1: 크리 히트 데미지 (CritMultiplier 적용)
    -- Pass 2: 일반 히트 데미지
    cfg.skillCond["CriticalStrike"] = (pass == 1)
end
```

크리/비크리 각각의 데미지를 별도로 계산한 뒤 가중 평균.

---

## 7. 명중률 (Hit Chance) 계산

**코드 위치:** `CalcDefence.lua:32-38`

```lua
function calcs.hitChance(evasion, accuracy)
    if accuracy < 0 then return 5 end
    local rawChance = accuracy / (accuracy + (evasion / 5) ^ 0.9) * 125
    return max(min(round(rawChance), 100), 5)
end
```

**공식:**
```
HitChance = Accuracy / (Accuracy + (Evasion / 5) ^ 0.9) * 125
```

- 최소 5%, 최대 100%
- 명중률 음수 시 강제 5%

---

## 8. 적 저항 및 데미지 경감

### 8.1 아머에 의한 물리 데미지 경감

**코드 위치:** `CalcDefence.lua:41-51`

```lua
function calcs.armourReductionF(armour, raw)
    return armour / (armour + raw * 5) * 100
end
```

**공식:**
```
데미지 경감(%) = Armour / (Armour + RawDamage × 5) × 100
```

- 입는 데미지가 클수록 아머의 효과가 감소
- `DamageReductionMax`로 상한 존재

### 8.2 저항 적용

```lua
-- CalcDefence.lua:81-83
resist = output[damageType.."Resist"]
resMult = 1 - resist / 100
```

**공식:**
```
저항 배율 = 1 - 저항(%) / 100
```

예시: Fire 저항 75% → `resMult = 0.25` → 데미지 75% 감소

### 8.3 데미지 관통 (Penetration)

적의 저항을 무시하는 메커니즘:

```
유효 저항 = 적_저항 - 관통값
```

### 8.4 "Damage Taken As" 전환

**코드 위치:** `CalcDefence.lua:58-112`

받는 데미지의 타입을 변환하는 시스템:

```lua
-- 각 타입별 "Taken As" 비율 수집
shiftTable[damageType] = Sum("BASE", nil, sourceType.."DamageTakenAs"..damageType, ...)

-- 원본 타입에 남는 비율
damageTakenAs = max(1 - totalTakenAs/100, 0)  -- 원본 타입인 경우
damageTakenAs = shiftTable[damageType] / 100    -- 전환 대상 타입인 경우
```

### 8.5 전체 받는 데미지 공식

```
최종 받는 데미지 = BaseDamage × DamageTakenAs비율
                   × (1 - Resist/100)
                   × (1 - min(DamageReductionMax, ArmourReduction + FlatReduction) / 100)
                   × max((1 + DamageTakenINC/100) × DamageTakenMORE, 0)
```

---

## 9. DoT (Damage over Time) 계산

### 9.1 출혈 (Bleed)

**코드 위치:** `CalcOffence.lua:4059-4258`

```
BleedDPS = AverageBleedDamage × BleedBasePercent/100 × 특수배율
```

- `BleedBasePercent` — 데이터 파일에서 정의된 기본 출혈 비율 (`data.misc.BleedPercentBase`)
- 물리 데미지 기반
- 스택 가능: `BleedStacksMax`로 최대 스택 수 제한
- 지속시간: `BleedDurationBase` × 지속시간 모디파이어
- DPS 캡 존재: `min(BleedDPSUncapped, data.misc.DotDpsCap)`

**출혈 데미지 소스:**
```lua
min, max = calcAilmentSourceDamage(..., "Physical", 0)
```

### 9.2 중독 (Poison)

- 카오스 + 물리 데미지 기반
- 스택 가능 (기본 무제한)
- 지속시간 × 공격 속도로 총 스택 수 결정
- 각 스택의 DPS 합산

### 9.3 점화 (Ignite)

- 화염 데미지 기반
- 기본적으로 비스택 (특수 패시브로 스택 가능)
- 가장 강한 점화만 적용 (기본)

### 9.4 Ailment 데미지 소스 계산

**코드 위치:** `CalcOffence.lua:141-150`

```lua
function calcAilmentSourceDamage(activeSkill, output, cfg, breakdown, damageType, typeFlags)
    local min, max = calcDamage(...)
    local convMult = conversionTable[damageType].mult  -- 전환되지 않고 남은 비율
    return min * convMult, max * convMult
end
```

Ailment의 소스 데미지는 해당 타입에서 **전환되지 않고 남은** 데미지만 사용.

---

## 10. 최종 DPS 산출

### 10.1 히트 DPS

```
AverageDamage = (DamageMin + DamageMax) / 2
AverageDamage × CritEffect                          -- 크리 유효 배율 적용
HitDPS = AverageDamage × HitRate                     -- 초당 히트 수
```

### 10.2 총 DPS

```
TotalDPS = HitDPS + BleedDPS + PoisonDPS + IgniteDPS + ...
```

**코드 위치:** `Calcs.lua:424`
```lua
fullDPS = calcs.calcFullDPS(build, "CALCULATOR", ...)
-- 모든 FullDPS 등록 스킬의 DPS를 합산
```

### 10.3 FullDPS 시스템

여러 스킬의 DPS를 합산하는 시스템:
- `SkillDPS` — 각 스킬별 DPS
- `FullDPS` — 합산 DPS
- `FullDotDPS` — DoT 합산 DPS

---

## 부록: 핵심 공식 요약표

| 항목 | 공식 |
|------|------|
| **히트 데미지** | `((Base × INC × MORE) × GenericMore + ConvertedAdd) × TypeMore` |
| **명중률** | `Accuracy / (Accuracy + (Evasion/5)^0.9) × 125` |
| **아머 경감** | `Armour / (Armour + Damage × 5) × 100` |
| **유효 크리 배율** | `(1 - CritChance%) + CritChance% × CritMultiplier` |
| **저항 배율** | `1 - Resist% / 100` |
| **데미지 경감 배율** | `1 - min(MaxReduction, ArmourReduction + FlatReduction) / 100` |
| **받는 데미지** | `BaseDmg × ResMult × ReductMult × DamageTakenMods` |
| **Lucky 크리** | `1 - (1 - CritChance/100) ^ (rolls+1)` |

---

## 부록: 주요 코드 참조

| 기능 | 파일 | 라인 |
|------|------|------|
| 계산 엔트리 포인트 | `Calcs.lua` | 416 |
| 모듈 로드 | `Calcs.lua` | 13-21 |
| 데미지 타입/플래그 정의 | `CalcOffence.lua` | 30-44 |
| `calcDamage()` 핵심 함수 | `CalcOffence.lua` | 68-139 |
| `calcAilmentSourceDamage()` | `CalcOffence.lua` | 141-150 |
| 전환 테이블 구축 | `CalcOffence.lua` | 1840-1883 |
| 크리 확률 계산 | `CalcOffence.lua` | 2826-2966 |
| 크리 배율 계산 | `CalcOffence.lua` | 2995-3001 |
| Two-Pass 히트 계산 | `CalcOffence.lua` | 3100-3190 |
| 출혈 계산 | `CalcOffence.lua` | 4059-4258 |
| 명중률 공식 | `CalcDefence.lua` | 32-38 |
| 아머 경감 공식 | `CalcDefence.lua` | 41-51 |
| 받는 데미지 전환 | `CalcDefence.lua` | 58-112 |
