# TaskState Vault 鍒濆浣跨敤鎸囧紩

## 灞傜骇鍚嶇О

```text
TaskState Vault:
  椤圭洰姝ｅ紡鍚嶃€?
ContextKernel:
  鎵ц妯″紡銆丳roject Governor銆佷换鍔″浘銆佹墽琛岄槦鍒椼€佷换鍔＄洰鏍囨敼鍐欍€佽繍琛岀姸鎬佸拰涓婁笅鏂囧姞杞姐€?
TaskFS:
  `.taskstate-vault` 涓嬬殑璐︽埛銆侀鍩熴€侀」鐩€佷换鍔°€佽繍琛屾枃浠剁粨鏋勩€?
TaskDB:
  SQLite 绱㈠紩銆丗TS銆佹寚閽堛€佸鍏ュ壇鏈拰椤圭洰鏂囦欢绱㈠紩銆?```

## 鍚姩鍒ゆ柇

```text
simple_task:
  鐭€佹槑纭€佸崟姝ユ垨灏戞暟姝ラ锛屼笉寮哄埗椤圭洰鍥俱€?
managed_task:
  闇€瑕佽繛缁姸鎬併€佽瘉鎹€侀敊璇€佷骇鐗╋紝浣嗕笉鏄鏉傞」鐩€?
complex_project:
  澶氭ā鍧椼€佸闃舵銆侀暱鏈熴€佹槗璺戝亸銆佹湁渚濊禆锛屽繀椤讳娇鐢?Project Governor銆?
program_scale:
  澶氶」鐩€佸宸ヤ綔娴併€侀暱鏈熻矾绾垮浘銆佽法椤圭洰渚濊禆銆?```

## complex_project 蹇呰鏂囦欢

```text
PROJECT_INTENT.yaml
PROJECT_MODEL.yaml
PROJECT_PROGRESS.yaml
GOVERNOR/TASK_GRAPH.jsonl
GOVERNOR/EXECUTION_QUEUE.jsonl
GOVERNOR/BLOCKERS.jsonl
GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl
褰撳墠 TASK_STATE.yaml
褰撳墠 NEXT_ACTION.md
```

## complex_project 鎵ц娴佺▼

```text
1. 璇诲彇 PROJECT_INTENT锛岀‘璁ゆ渶楂樼洰鏍囥€?2. 璇诲彇 PROJECT_PROGRESS锛屼簡瑙ｅ綋鍓嶉」鐩€佸娍銆?3. 璇诲彇 EXECUTION_QUEUE锛岄€夋嫨褰撳墠鏈€浼樹换鍔°€?4. 璇诲彇 TASK_GRAPH 鐩稿叧瀛愬浘锛岀悊瑙ｄ緷璧栧拰闃诲銆?5. 鎵撳紑褰撳墠 TASK_STATE 鍜?NEXT_ACTION銆?6. 鎵ц褰撳墠浠诲姟銆?7. 璁板綍璇佹嵁銆佷骇鐗┿€侀敊璇€佸喅绛栥€?8. 鏇存柊浠诲姟鍥捐妭鐐圭姸鎬併€?9. 蹇呰鏃跺啓 OBJECTIVE_CHANGE_LOG銆?10. 鏇存柊 PROJECT_PROGRESS銆?11. 閲嶆帓 EXECUTION_QUEUE銆?12. 鏇存柊 NEXT_ACTION銆?13. 鍚屾 TaskFS 璁板綍鍜?TaskDB 绱㈠紩銆?```

