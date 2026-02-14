# MCP Server Layer Implementation Plan for PathOfBuilding

## 프로젝트 개요

PathOfBuilding에 MCP (Model Context Protocol) 서버 레이어를 추가하여 다음 기능을 외부에서 접근 가능하게 만듭니다:

1. **캐릭터 DPS 조회**: 등록된 빌드의 현재 effective DPS 및 상세 통계
2. **장비 변경 시뮬레이션**: 특정 장비를 교체했을 때의 DPS 변화 계산

---

## 코드베이스 분석 요약

### 핵심 구조
- **언어**: Lua (LuaJIT 5.1)
- **타입**: 데스크톱 GUI 애플리케이션
- **데이터 저장**: XML 기반 빌드 파일

### 주요 모듈
| 모듈 | 역할 |
|------|------|
| `/src/Modules/Calcs.lua` | DPS 계산 메인 API |
| `/src/Modules/Build.lua` | 빌드 로딩/저장 로직 |
| `/src/Classes/Item.lua` | 아이템 파싱 및 관리 |
| `/src/Classes/ItemsTab.lua` | 장비 슬롯 및 아이템 셋 관리 |
| `/src/HeadlessWrapper.lua` | CLI/Headless 실행 지원 (MCP 통합 시작점) |
| `/runtime/lua/dkjson.lua` | JSON 처리 라이브러리 |

### DPS 계산 흐름
```lua
calcs.buildOutput(build, mode)
  → CalcSetup: 아이템/스킬/패시브 트리 초기화
  → CalcPerform: 모든 modifier 적용
  → CalcOffence: 데미지 계산 (hit, DoT, ailment)
  → CalcDefence: 방어 계산 (life, ES, armor, evasion)
  → 결과 반환 (TotalDPS, CombinedDPS, 방어 스탯 등)
```

### 장비 관리 구조
```lua
build.itemsTab.slots["Weapon 1"]  -- 슬롯별 아이템
build.itemsTab.activeItemSet      -- 현재 활성 아이템 셋
Item:ParseRaw(itemText)           -- 게임 아이템 텍스트 파싱
```

---

## MCP 서버 아키텍처 설계

### 디렉토리 구조
```
/mcp-server/
├── init.lua                  # MCP 서버 초기화 및 메인 루프
├── protocol.lua              # MCP JSON-RPC 프로토콜 핸들러
├── handlers/
│   ├── dps_handler.lua       # DPS 조회 기능
│   ├── equipment_handler.lua # 장비 변경 시뮬레이션
│   └── build_handler.lua     # 빌드 로딩/관리
├── utils/
│   ├── build_loader.lua      # XML 빌드 파일 로더
│   └── response_builder.lua  # JSON 응답 생성
└── package.json              # MCP 서버 메타데이터 (Node.js 스타일)
```

### MCP 통신 프로토콜
- **전송 방식**: JSON-RPC 2.0 over stdio
- **요청 형식**:
  ```json
  {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_character_dps",
      "arguments": { "build_name": "MyBuild" }
    }
  }
  ```

### 노출할 MCP Tools

#### 1. `get_character_dps`
**설명**: 지정된 빌드의 현재 DPS 및 방어 통계 반환

**입력**:
```json
{
  "build_name": "MyBuild",           // 빌드 파일명 또는 경로
  "skill_index": 1,                  // (선택) 계산할 스킬 그룹 인덱스 (기본값: 1번 스킬 그룹)
  "boss_type": "Pinnacle",           // (선택) 보스 타입: "None", "Boss", "Pinnacle", "Uber" (기본값: "None")
  "calculation_mode": "EFFECTIVE"    // (선택) 계산 모드: "UNBUFFED", "BUFFED", "COMBAT", "EFFECTIVE" (기본값: "EFFECTIVE")
}
```

**출력 필드 설명**:
```json
{
  "character": {
    "name": "MyBuild",               // 빌드 이름
    "level": 95,                     // 캐릭터 레벨
    "class": "Shadow",               // 기본 클래스
    "ascendancy": "Assassin"         // 승급 클래스
  },

  "config": {
    "boss_type": "Pinnacle",         // 적용된 보스 타입
    "calculation_mode": "EFFECTIVE"  // 적용된 계산 모드
  },

  // === DPS 통계 ===
  "dps": {
    // --- 메인 DPS 지표 ---
    "total_dps": 5234567.89,         // 스킬의 순수 히트 DPS (초당 데미지, DoT 제외)
                                     // = AverageHit × HitRate (attack/cast speed × hit chance)

    "combined_dps": 6123456.78,      // 히트 + 지속 데미지(DoT) 종합 DPS
                                     // 실제 전투에서 적에게 가하는 초당 총 데미지

    "total_dot_dps": 888888.89,      // 모든 지속 데미지(DoT) 합계
                                     // Ignite + Poison + Bleed + 기타 DoT 효과

    "average_hit": 123456.78,        // 단일 히트의 평균 데미지
                                     // 크리티컬 확률 고려한 기댓값

    // --- 상태이상(Ailment) DPS ---
    "ailments": {
      "ignite_dps": 234567.89,       // 화상(Ignite) 초당 데미지
      "poison_dps": 456789.12,       // 중독(Poison) 초당 데미지 (모든 스택 합계)
      "bleed_dps": 197531.88,        // 출혈(Bleed) 초당 데미지
      "total_poison_stacks": 15      // 평균 중독 스택 수
    },

    // --- 공격/시전 속도 ---
    "speed": {
      "attack_rate": 6.5,            // 초당 공격 횟수 (attack 스킬인 경우)
      "cast_rate": 4.2,              // 초당 시전 횟수 (spell 스킬인 경우)
      "hit_chance": 100.0            // 명중률 (%)
    }
  },

  // === 방어 통계 ===
  "defense": {
    // --- 생명력/에너지 실드 ---
    "life": 4567,                    // 최대 생명력
    "energy_shield": 2345,           // 최대 에너지 실드
    "mana": 1234,                    // 최대 마나
    "total_pool": 6912,              // 총 생존력 (Life + ES)

    // --- 물리 방어 ---
    "evasion": 45678,                // 회피력 수치
    "evasion_chance": 68.5,          // 회피 확률 (%)
    "armor": 12345,                  // 방어력 수치
    "physical_reduction": 35.2,      // 물리 피해 감소율 (%) - 보통 공격 기준

    // --- 블록 ---
    "block_chance": 45.5,            // 공격 블록 확률 (%)
    "spell_block_chance": 30.0,      // 주문 블록 확률 (%)

    // --- 저항 ---
    "resistances": {
      "fire": 75,                    // 화염 저항 (%)
      "cold": 75,                    // 냉기 저항 (%)
      "lightning": 75,               // 번개 저항 (%)
      "chaos": -15                   // 카오스 저항 (%)
    },

    // --- EHP (Effective Hit Points) ---
    "ehp": {
      "physical": 125000,            // 물리 데미지 EHP
      "elemental": 180000,           // 원소 데미지 평균 EHP
      "chaos": 95000                 // 카오스 데미지 EHP
    }
  },

  // === 스킬 정보 ===
  "active_skill": {
    "name": "Blade Vortex",          // 활성 스킬 이름
                                     // 현재 계산에 사용된 메인 스킬
                                     // 빌드에 여러 스킬이 있을 때 이 필드로 구분

    "socket_group": 1,               // 소켓 그룹 번호 (1~N)
    "skill_type": "Spell",           // 스킬 유형: "Attack", "Spell", "Minion" 등
    "mana_cost": 45,                 // 마나 소모량
    "skill_part": "Default"          // 스킬 파트 (일부 스킬은 여러 파트로 나뉨)
  }
}
```

**여러 스킬이 있을 때 처리 방법**:
1. **기본 동작**: `skill_index` 미지정 시 첫 번째 스킬 그룹 사용
2. **특정 스킬 선택**: `skill_index` (1~N)로 원하는 소켓 그룹 지정
3. **모든 스킬 조회**: `skill_index: "all"` 사용 시 배열로 각 스킬의 DPS 반환
   ```json
   {
     "skills": [
       { "active_skill": { "name": "Blade Vortex", ... }, "dps": {...}, "defense": {...} },
       { "active_skill": { "name": "Blade Blast", ... }, "dps": {...}, "defense": {...} }
     ]
   }
   ```

**보스별 DPS 계산**:
- **"None"** (기본): 일반 몬스터 대상 (레벨 83, 저항 0%)
- **"Boss"**: 표준 보스 (상태이상 임계치 +488%, 저항 40%)
- **"Pinnacle"**: 가디언/핀나클 보스 (Maven, Shaper 등, 레벨 84, 저항 50%)
- **"Uber"**: 우버 핀나클 보스 (받는 데미지 -70%, 레벨 85)

보스 타입에 따라 `total_dps`, `combined_dps`, `ailments` 값이 크게 달라짐 (저항/임계치 적용).

#### 2. `simulate_equipment_change`
**설명**: 특정 슬롯의 장비를 교체했을 때 DPS 및 방어력 변화 계산

**입력**:
```json
{
  "build_name": "MyBuild",
  "slot": "Weapon 1",               // "Helmet", "Body Armour", "Gloves", "Boots", "Ring 1", etc.
  "item_text": "Rarity: Rare\n...", // 게임에서 복사한 아이템 텍스트
  "keep_changes": false,            // (선택) true면 빌드에 영구 적용
  "boss_type": "Pinnacle",          // (선택) 보스 타입 (get_character_dps와 동일)
  "calculation_mode": "EFFECTIVE"   // (선택) 계산 모드
}
```

**출력** (get_character_dps의 전체 구조를 before/after로 반환):
```json
{
  // === 변경 전 통계 (전체) ===
  "before": {
    "item_name": "Current Weapon",
    "item_rarity": "Rare",

    // get_character_dps와 동일한 구조
    "character": { "name": "MyBuild", "level": 95, "class": "Shadow", "ascendancy": "Assassin" },
    "config": { "boss_type": "Pinnacle", "calculation_mode": "EFFECTIVE" },

    "dps": {
      "total_dps": 5234567.89,
      "combined_dps": 6123456.78,
      "total_dot_dps": 888888.89,
      "average_hit": 123456.78,
      "ailments": { "ignite_dps": 234567.89, "poison_dps": 456789.12, "bleed_dps": 197531.88 },
      "speed": { "attack_rate": 6.5, "hit_chance": 100.0 }
    },

    "defense": {
      "life": 4567,
      "energy_shield": 2345,
      "mana": 1234,
      "total_pool": 6912,
      "evasion": 45678,
      "evasion_chance": 68.5,
      "armor": 12345,
      "physical_reduction": 35.2,
      "block_chance": 45.5,
      "spell_block_chance": 30.0,
      "resistances": { "fire": 75, "cold": 75, "lightning": 75, "chaos": -15 },
      "ehp": { "physical": 125000, "elemental": 180000, "chaos": 95000 }
    },

    "active_skill": { "name": "Blade Vortex", "socket_group": 1, "skill_type": "Spell" }
  },

  // === 변경 후 통계 (전체) ===
  "after": {
    "item_name": "New Weapon",
    "item_rarity": "Unique",

    "character": { "name": "MyBuild", "level": 95, "class": "Shadow", "ascendancy": "Assassin" },
    "config": { "boss_type": "Pinnacle", "calculation_mode": "EFFECTIVE" },

    "dps": {
      "total_dps": 6123456.78,
      "combined_dps": 7234567.89,
      "total_dot_dps": 1111111.00,
      "average_hit": 145678.90,
      "ailments": { "ignite_dps": 278901.23, "poison_dps": 612345.67, "bleed_dps": 219864.10 },
      "speed": { "attack_rate": 7.2, "hit_chance": 100.0 }
    },

    "defense": {
      "life": 4567,
      "energy_shield": 2345,
      "mana": 1234,
      "total_pool": 6912,
      "evasion": 43210,
      "evasion_chance": 66.8,
      "armor": 11000,
      "physical_reduction": 33.5,
      "block_chance": 50.0,
      "spell_block_chance": 30.0,
      "resistances": { "fire": 75, "cold": 75, "lightning": 75, "chaos": -10 },
      "ehp": { "physical": 130000, "elemental": 180000, "chaos": 98000 }
    },

    "active_skill": { "name": "Blade Vortex", "socket_group": 1, "skill_type": "Spell" }
  },

  // === 변화량 요약 ===
  "delta": {
    "dps": {
      "total_dps": { "absolute": 888888.89, "percent": 16.98 },
      "combined_dps": { "absolute": 1111111.11, "percent": 17.85 },
      "average_hit": { "absolute": 22222.12, "percent": 18.0 }
    },
    "defense": {
      "life": { "absolute": 0, "percent": 0 },
      "total_pool": { "absolute": 0, "percent": 0 },
      "armor": { "absolute": -1345, "percent": -10.9 },
      "evasion": { "absolute": -2468, "percent": -5.4 },
      "block_chance": { "absolute": 4.5, "percent": 9.9 },
      "physical_ehp": { "absolute": 5000, "percent": 4.0 }
    }
  }
}
```

**참고**: `recommendation` 필드는 제거됨. 클라이언트가 delta 값을 보고 직접 판단.

#### 3. `list_builds`
**설명**: 사용 가능한 빌드 목록 반환

**입력**:
```json
{}
```

**출력**:
```json
{
  "builds": [
    {
      "name": "MyBuild",
      "path": "/path/to/Builds/MyBuild.xml",
      "class": "Shadow",
      "level": 95,
      "last_modified": "2026-02-14T10:30:00Z"
    }
  ]
}
```

#### 4. `compare_items`
**설명**: 여러 아이템을 동시에 비교 (동일 슬롯)

**입력**:
```json
{
  "build_name": "MyBuild",
  "slot": "Ring 1",
  "items": [
    "Rarity: Rare\n...",            // 아이템 1
    "Rarity: Unique\n..."           // 아이템 2
  ],
  "boss_type": "Pinnacle",          // (선택) 보스 타입
  "calculation_mode": "EFFECTIVE"   // (선택) 계산 모드
}
```

**출력**:
```json
{
  "current": {
    "item_name": "Current Ring",
    "total_dps": 5800000,
    "combined_dps": 6500000,
    "life": 4567,
    "total_pool": 6912
  },

  "comparisons": [
    {
      "index": 0,
      "item_name": "Steel Ring",
      "item_rarity": "Rare",
      "total_dps": 6000000,
      "combined_dps": 6750000,
      "life": 4567,
      "total_pool": 6912,
      "delta_from_current": {
        "total_dps": { "absolute": 200000, "percent": 3.45 },
        "combined_dps": { "absolute": 250000, "percent": 3.85 },
        "life": { "absolute": 0, "percent": 0 }
      }
    },
    {
      "index": 1,
      "item_name": "Le Heup of All",
      "item_rarity": "Unique",
      "total_dps": 5900000,
      "combined_dps": 6600000,
      "life": 4567,
      "total_pool": 6912,
      "delta_from_current": {
        "total_dps": { "absolute": 100000, "percent": 1.72 },
        "combined_dps": { "absolute": 100000, "percent": 1.54 },
        "life": { "absolute": 0, "percent": 0 }
      }
    }
  ]
}
```

**참고**: `best_option` 필드 제거. 클라이언트가 각 아이템의 `delta_from_current`를 보고 직접 판단.

---

## 구현 단계

### Phase 1: MCP 기본 인프라 구축
**목표**: stdio 기반 MCP 서버 스켈레톤 생성

**작업**:
1. `/mcp-server/init.lua` 생성
   - stdio 읽기/쓰기 루프 구현
   - JSON-RPC 2.0 요청 파싱
   - MCP 프로토콜 초기화 (capabilities, tools 목록 노출)

2. `/mcp-server/protocol.lua` 생성
   - `initialize` 요청 핸들러
   - `tools/list` 핸들러 (4개 tool 정의 반환)
   - `tools/call` 라우터 (tool 이름별 핸들러 매핑)

3. HeadlessWrapper 통합
   - `/src/HeadlessWrapper.lua` 확장
   - MCP 서버 모드 추가: `--mcp-server` CLI 플래그
   - 그래픽 스텁 활성화 + MCP 서버 시작

**검증**:
```bash
lua Launch.lua --mcp-server
# stdin/stdout으로 MCP 통신 확인
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | lua Launch.lua --mcp-server
```

---

### Phase 2: 빌드 로딩 및 DPS 계산 기능
**목표**: `get_character_dps` tool 구현

**작업**:
1. `/mcp-server/utils/build_loader.lua` 생성
   - XML 빌드 파일 로딩 (`LoadModule` 활용)
   - 빌드 디렉토리 스캔 (기본 경로: `~/Path of Building/Builds/`)
   - 빌드 객체 메모리 캐싱

2. `/mcp-server/handlers/dps_handler.lua` 생성
   - `calcs.buildOutput(build, "BUILD")` 호출
   - `env.player.output` 에서 DPS 데이터 추출
   - JSON 응답 포맷팅

3. 통합
   - `protocol.lua`에서 `tools/call` → `get_character_dps` 라우팅
   - 에러 처리 (빌드 없음, 계산 실패 등)

**검증**:
```json
// Request
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "get_character_dps",
    "arguments": { "build_name": "TestBuild" }
  }
}

// Expected: DPS 데이터 포함 응답
```

---

### Phase 3: 장비 변경 시뮬레이션
**목표**: `simulate_equipment_change` tool 구현

**작업**:
1. `/mcp-server/handlers/equipment_handler.lua` 생성
   - 현재 DPS 계산 (Before)
   - `Item:ParseRaw(itemText)` 로 새 아이템 파싱
   - 슬롯에 임시 아이템 할당
   - 새 DPS 계산 (After)
   - 변경사항 롤백 또는 적용 (`keep_changes` 플래그)

2. 에러 처리
   - 잘못된 슬롯 이름
   - 아이템 파싱 실패
   - 호환되지 않는 아이템 (예: 무기를 헬멧 슬롯에)

**검증**:
- 알려진 업그레이드 아이템으로 테스트
- DPS 증가 확인
- 빌드 파일 변경되지 않음 확인 (keep_changes=false)

---

### Phase 4: 추가 기능 및 최적화
**목표**: `list_builds`, `compare_items` 구현 + 성능 개선

**작업**:
1. `/mcp-server/handlers/build_handler.lua` 생성
   - 빌드 디렉토리 스캔
   - 메타데이터 추출 (레벨, 클래스, 수정 시간)

2. `compare_items` 구현
   - 여러 아이템 루프 처리
   - 결과 정렬 (DPS 기준)

3. 캐싱 레이어
   - 빌드 객체 메모리 캐싱 (파일 수정 시간 기반 무효화)
   - 계산 결과 캐싱 (아이템 변경 없으면 재사용)

4. 로깅
   - 디버그 모드 추가 (`--mcp-debug`)
   - stderr로 로그 출력 (stdout은 MCP 프로토콜용)

---

### Phase 5: 문서화 및 배포
**목표**: 사용자 문서 작성, 패키징

**작업**:
1. `/mcp-server/README.md` 작성
   - MCP 클라이언트 연결 방법
   - Tool 사용 예제
   - 문제 해결 가이드

2. MCP 메타데이터 파일 생성
   - `package.json` 또는 `mcp.json` (MCP 표준에 따라)
   - 서버 이름, 버전, 설명 정의

3. 테스트 스크립트
   - `/mcp-server/test/` 디렉토리 생성
   - 각 tool별 자동화 테스트

4. CI/CD 통합 (선택)
   - GitHub Actions에서 MCP 서버 테스트

---

## 기술적 고려사항

### 1. Lua 환경에서 stdio 처리
**문제**: Lua는 비동기 I/O가 제한적

**해결**:
- `io.stdin:read("*l")` 로 줄 단위 블로킹 읽기
- `io.stdout:write()` + `io.flush()` 로 즉시 응답
- 간단한 동기 모델로 충분 (MCP는 요청-응답 패턴)

### 2. PathOfBuilding 초기화 오버헤드
**문제**: 매 요청마다 전체 데이터 로딩 시 느림

**해결**:
- 서버 시작 시 한 번만 데이터 로딩 (`/src/Data/` 모듈들)
- 빌드 객체만 요청별로 로드/언로드
- LRU 캐시로 최근 빌드 N개 메모리 유지

### 3. 아이템 파싱 정확도
**문제**: 게임 업데이트로 아이템 형식 변경 가능

**해결**:
- `Item:ParseRaw()`는 이미 정규식 기반 강건한 파서
- 파싱 실패 시 명확한 에러 메시지 반환
- 로그에 파싱 실패한 아이템 텍스트 기록

### 4. 멀티 빌드 동시 처리
**문제**: Lua는 싱글 스레드

**해결**:
- 현재 요구사항에서는 순차 처리로 충분
- 필요시 여러 MCP 서버 프로세스 실행 (빌드별 격리)

### 5. 에러 핸들링
**MCP 에러 응답 형식**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "Build not found",
    "data": { "build_name": "NonExistent" }
  }
}
```

**에러 코드 정의**:
- `-32700`: JSON 파싱 에러
- `-32600`: 잘못된 요청
- `-32601`: 메소드 없음
- `-32000`: 빌드 로딩 실패
- `-32001`: 아이템 파싱 실패
- `-32002`: 계산 실패

---

## 파일 위치 정리

### 새로 생성할 파일
```
/mcp-server/
├── init.lua                      # MCP 서버 메인 진입점
├── protocol.lua                  # JSON-RPC 2.0 핸들러
├── handlers/
│   ├── dps_handler.lua           # DPS 조회
│   ├── equipment_handler.lua     # 장비 시뮬레이션
│   └── build_handler.lua         # 빌드 관리
├── utils/
│   ├── build_loader.lua          # 빌드 로딩 유틸
│   └── response_builder.lua      # JSON 응답 생성
├── test/
│   ├── test_dps.lua              # DPS 계산 테스트
│   └── test_equipment.lua        # 장비 변경 테스트
├── README.md                     # 사용 설명서
└── package.json                  # MCP 메타데이터
```

### 수정할 기존 파일
```
/src/HeadlessWrapper.lua          # --mcp-server 플래그 추가
/Launch.lua                       # MCP 서버 모드 분기
```

---

## 사용 예시

### MCP 클라이언트에서 호출
```javascript
// Claude Desktop 또는 다른 MCP 클라이언트
const mcpClient = new MCPClient({
  command: 'lua',
  args: ['Launch.lua', '--mcp-server'],
  cwd: '/path/to/PathOfBuilding'
});

// DPS 조회
const dps = await mcpClient.callTool('get_character_dps', {
  build_name: 'MyAssassin'
});
console.log(`Total DPS: ${dps.dps.total_dps}`);

// 장비 변경 시뮬레이션
const change = await mcpClient.callTool('simulate_equipment_change', {
  build_name: 'MyAssassin',
  slot: 'Weapon 1',
  item_text: 'Rarity: Rare\n...'
});
console.log(`DPS Change: ${change.delta.percent}%`);
```

---

## 타임라인 (추정)

| Phase | 작업 | 예상 소요 |
|-------|------|----------|
| Phase 1 | MCP 인프라 구축 | 2-3일 |
| Phase 2 | DPS 조회 기능 | 2일 |
| Phase 3 | 장비 시뮬레이션 | 3-4일 |
| Phase 4 | 추가 기능 | 2일 |
| Phase 5 | 문서화/테스트 | 1-2일 |
| **Total** | | **10-14일** |

---

## 다음 단계

1. ✅ **계획 검토** - 이 계획서 확인
2. ⬜ **Phase 1 시작** - MCP 기본 인프라 구축
3. ⬜ **초기 테스트** - stdio 통신 검증
4. ⬜ **DPS 기능 구현** - Phase 2
5. ⬜ **장비 시뮬레이션** - Phase 3
6. ⬜ **통합 테스트** - 실제 빌드로 검증

---

## 참고 자료

- **MCP Specification**: https://spec.modelcontextprotocol.io/
- **JSON-RPC 2.0**: https://www.jsonrpc.org/specification
- **PathOfBuilding Source**: `/src/` 디렉토리 전체
- **Lua JSON Library**: `/runtime/lua/dkjson.lua`

---

## 질문 및 결정 사항

1. **빌드 저장 경로**: 기본 경로 사용 vs. 사용자 지정 경로 지원?
   - **결정**: 기본 경로 + `--builds-dir` CLI 옵션 추가

2. **캐싱 전략**: 메모리 사용량 vs. 성능?
   - **결정**: 최대 5개 빌드 LRU 캐시

3. **아이템 변경 영구 적용**: 기본값 true vs. false?
   - **결정**: 기본값 `false` (안전성 우선)

4. **MCP 서버 포트**: stdio vs. HTTP?
   - **결정**: stdio (MCP 표준, 방화벽 이슈 없음)

---

*이 계획서는 PathOfBuilding에 MCP 서버 레이어를 추가하기 위한 전체 로드맵입니다. 각 단계는 독립적으로 테스트 가능하며, 점진적으로 기능을 확장할 수 있습니다.*
