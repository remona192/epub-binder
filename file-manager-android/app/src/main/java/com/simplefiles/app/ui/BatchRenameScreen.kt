@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package com.simplefiles.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.KeyboardArrowDown
import androidx.compose.material.icons.outlined.KeyboardArrowUp
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import com.simplefiles.core.BatchRenamer
import com.simplefiles.core.CaseMode
import com.simplefiles.core.NaturalOrder
import com.simplefiles.core.RenameInput
import com.simplefiles.core.RenamePlan
import com.simplefiles.core.RenamePostOptions
import com.simplefiles.core.RenameRule
import com.simplefiles.core.TextPosition
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.File

private data class RuleSlot(val id: Long, val rule: RenameRule)

private enum class OrderBy(val label: String) { NAME("이름순"), DATE("날짜순"), SELECTION("선택한 순서") }

private val ruleFactories: List<Pair<String, () -> RenameRule>> = listOf(
    "찾아 바꾸기 (정규식)" to { RenameRule.Replace() },
    "덮어쓰기 (새 이름)" to { RenameRule.Overwrite() },
    "뒤에 화수 붙이기" to { RenameRule.EpisodeSuffix() },
    "글자 넣기" to { RenameRule.Insert() },
    "글자 지우기" to { RenameRule.Remove() },
    "번호 붙이기" to { RenameRule.Numbering() },
    "이름 틀" to { RenameRule.Template("{name}") },
    "대소문자" to { RenameRule.ChangeCase() },
    "확장자 바꾸기" to { RenameRule.Extension() },
)

/** PC의 배치 네이머 / 이지네이머 같은 일괄 이름 변경 */
@Composable
fun BatchRenameScreen(vm: AppViewModel, paths: List<String>) {
    val slots = remember { mutableStateListOf(RuleSlot(0, RenameRule.Replace())) }
    var nextId by remember { mutableLongStateOf(1) }
    var includeExt by remember { mutableStateOf(false) }
    var order by remember { mutableStateOf(OrderBy.NAME) }
    var addMenu by remember { mutableStateOf(false) }
    // EPUB 바인더 일괄 변경의 후처리 옵션 (기본: 이름 정리 + 화수 보정 + 자소 분리 교정)
    var post by remember { mutableStateOf(RenamePostOptions.RECOMMENDED) }
    // 적용 범위: 체크 해제한 항목은 그대로 둔다
    val excluded = remember { mutableStateListOf<String>() }

    val baseInputs by produceState(emptyList<RenameInput>(), paths) {
        value = withContext(Dispatchers.IO) {
            paths.map { File(it) }.filter { it.exists() }.map { RenameInput(it.path, it.name, it.isDirectory, it.lastModified()) }
        }
    }
    val inputs = remember(baseInputs, order) {
        when (order) {
            OrderBy.NAME -> baseInputs.sortedWith { a, b -> NaturalOrder.compare(a.name, b.name) }
            OrderBy.DATE -> baseInputs.sortedBy { it.lastModified }
            OrderBy.SELECTION -> baseInputs
        }
    }
    val rules = slots.map { it.rule }
    val excludedSet = excluded.toSet()
    val plan by produceState<RenamePlan?>(null, inputs, rules, includeExt, post, excludedSet) {
        delay(120)
        val included = if (excludedSet.isEmpty()) null else inputs.map { it.path }.filter { it !in excludedSet }.toSet()
        value = withContext(Dispatchers.IO) {
            BatchRenamer.plan(inputs, rules, includeExt, post = post, included = included)
        }
    }

    fun update(i: Int, r: RenameRule) {
        slots[i] = slots[i].copy(rule = r)
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(vm.snackbar) },
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                navigationIcon = { IconButton(onClick = { vm.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로") } },
                title = { Text("일괄 이름 변경 (${inputs.size}개)") },
            )
        },
        bottomBar = {
            val p = plan
            val changes = p?.changes.orEmpty()
            val errors = p?.previews?.count { it.error != null } ?: 0
            Surface(color = cardColor, shadowElevation = 8.dp) {
                Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp)) {
                    Text(
                        when {
                            p == null -> "미리보기 계산 중…"
                            p.ruleError != null -> p.ruleError!!
                            errors > 0 -> "문제가 있는 항목 ${errors}개를 고쳐야 적용할 수 있습니다"
                            else -> "${changes.size}개 항목의 이름이 바뀝니다"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = if (p?.hasErrors == true) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(6.dp))
                    Button(
                        onClick = { vm.applyBatchRename(changes.map { File(it.input.path) to it.newName }) },
                        enabled = p != null && !p.hasErrors && changes.isNotEmpty(),
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("이름 바꾸기") }
                }
            }
        },
    ) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
            item {
                SectionCard {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("확장자까지 포함해서 바꾸기")
                            Text("끄면 이름 부분에만 규칙을 적용합니다", style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Switch(checked = includeExt, onCheckedChange = { includeExt = it })
                    }
                    Text("번호 순서", style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(start = 16.dp, top = 8.dp))
                    Row(Modifier.padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OrderBy.entries.forEach { o ->
                            FilterChip(selected = order == o, onClick = { order = o }, label = { Text(o.label) })
                        }
                    }
                }
            }
            item {
                SectionTitle("적용 옵션 (규칙 적용 뒤 자동 처리)")
                SectionCard {
                    PostSwitch("이름 정리", "빈 괄호 · 겹친 공백 · 중복 구분자(-- __) 정리", post.cleanup) {
                        post = post.copy(cleanup = it)
                    }
                    PostSwitch("화수 표기 보정", "12회차 · 12회 · #12 → 12화, 1~216화 → 1-216화, 03권 → 3권", post.unifyEpisode) {
                        post = post.copy(unifyEpisode = it)
                    }
                    PostSwitch("자소 분리 교정", "풀어진 한글(ㄴㅐㄱㅏ)을 완성형으로", post.fixJamo) {
                        post = post.copy(fixJamo = it)
                    }
                    PostSwitch("언더바를 공백으로", "텔레그램에서 받은 '제목_1권' → '제목 1권'", post.underscoreToSpace) {
                        post = post.copy(underscoreToSpace = it)
                    }
                }
            }
            item { SectionTitle("규칙 (위에서부터 차례로 적용)") }
            itemsIndexed(slots, key = { _, s -> s.id }) { i, slot ->
                RuleCard(
                    index = i,
                    count = slots.size,
                    rule = slot.rule,
                    onChange = { update(i, it) },
                    onUp = { if (i > 0) slots.add(i - 1, slots.removeAt(i)) },
                    onDown = { if (i < slots.lastIndex) slots.add(i + 1, slots.removeAt(i)) },
                    onRemove = { slots.removeAt(i) },
                )
                Spacer(Modifier.height(8.dp))
            }
            item {
                Box(Modifier.padding(horizontal = 12.dp)) {
                    OutlinedButton(onClick = { addMenu = true }, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Outlined.Add, null)
                        Spacer(Modifier.width(6.dp))
                        Text("규칙 추가")
                    }
                    DropdownMenu(expanded = addMenu, onDismissRequest = { addMenu = false }) {
                        ruleFactories.forEach { (label, make) ->
                            DropdownMenuItem(text = { Text(label) }, onClick = {
                                addMenu = false
                                slots.add(RuleSlot(nextId++, make()))
                            })
                        }
                    }
                }
            }
            item {
                val total = inputs.size
                val on = total - excludedSet.count { ex -> inputs.any { it.path == ex } }
                Row(
                    Modifier.fillMaxWidth().padding(start = 28.dp, end = 12.dp, top = 16.dp, bottom = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("미리보기 · 적용 범위", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("${on}/${total}개에 적용 (체크를 끄면 그 파일은 그대로)", style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    androidx.compose.material3.TextButton(onClick = {
                        if (excluded.isEmpty()) excluded.addAll(inputs.map { it.path }) else excluded.clear()
                    }) { Text(if (excluded.isEmpty()) "모두 해제" else "전체 선택") }
                }
            }
            val previews = plan?.previews.orEmpty()
            itemsIndexed(previews, key = { _, p -> p.input.path }) { i, p ->
                Row(
                    Modifier.cardItem(i, previews.size).padding(start = 4.dp, end = 16.dp, top = 4.dp, bottom = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                Checkbox(
                    checked = !p.excluded,
                    onCheckedChange = { on -> if (on) excluded.remove(p.input.path) else excluded.add(p.input.path) },
                )
                Column(Modifier.weight(1f).padding(vertical = 6.dp)) {
                    Text(
                        p.input.name,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textDecoration = if (p.changed) TextDecoration.LineThrough else null,
                    )
                    Text(
                        "→ " + p.newName,
                        style = MaterialTheme.typography.bodyMedium,
                        color = when {
                            p.error != null -> MaterialTheme.colorScheme.error
                            p.changed -> MaterialTheme.colorScheme.primary
                            else -> MaterialTheme.colorScheme.onSurface
                        },
                        fontWeight = if (p.changed) FontWeight.Medium else FontWeight.Normal,
                    )
                    p.error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
                }
                }
                if (i != previews.lastIndex) {
                    HorizontalDivider(Modifier.padding(horizontal = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
                }
            }
        }
    }
}

@Composable
private fun RuleCard(
    index: Int,
    count: Int,
    rule: RenameRule,
    onChange: (RenameRule) -> Unit,
    onUp: () -> Unit,
    onDown: () -> Unit,
    onRemove: () -> Unit,
) {
    SectionCard {
        Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("${index + 1}. ${rule.title}", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
            Switch(checked = rule.enabled, onCheckedChange = { onChange(rule.withEnabled(it)) })
            IconButton(onClick = onUp, enabled = index > 0) { Icon(Icons.Outlined.KeyboardArrowUp, "위로") }
            IconButton(onClick = onDown, enabled = index < count - 1) { Icon(Icons.Outlined.KeyboardArrowDown, "아래로") }
            IconButton(onClick = onRemove) { Icon(Icons.Outlined.Close, "삭제") }
        }
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            when (rule) {
                is RenameRule.Replace -> {
                    Field("찾을 내용", rule.find, mono = rule.regex) { onChange(rule.copy(find = it)) }
                    Field("바꿀 내용 (비우면 삭제)", rule.replacement, mono = rule.regex) { onChange(rule.copy(replacement = it)) }
                    FlowRow(verticalArrangement = Arrangement.Center) {
                        CheckOption("정규식", rule.regex) { onChange(rule.copy(regex = it)) }
                        CheckOption("대소문자 무시", rule.ignoreCase) { onChange(rule.copy(ignoreCase = it)) }
                    }
                    if (rule.regex) {
                        Hint("예) ^\\[(.+?)\\]\\s*(.+)$ → $2 - $1   (괄호 그룹은 $1, $2…로 참조)\n\\d+ 숫자, \\s 공백, . 아무 글자, ^ 처음, $ 끝")
                    }
                }
                is RenameRule.Insert -> {
                    Field("넣을 글자", rule.text) { onChange(rule.copy(text = it)) }
                    PositionChips(rule.position, allowIndex = true) { onChange(rule.copy(position = it)) }
                    if (rule.position == TextPosition.INDEX) {
                        NumberField("위치 (0 = 맨 앞)", rule.index) { onChange(rule.copy(index = it)) }
                    }
                }
                is RenameRule.Remove -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NumberField(if (rule.fromEnd) "뒤에서 몇 번째부터 (0부터)" else "몇 번째부터 (0부터)", rule.start, Modifier.weight(1f)) {
                            onChange(rule.copy(start = it))
                        }
                        NumberField("글자 수", rule.count, Modifier.weight(1f)) { onChange(rule.copy(count = it)) }
                    }
                    CheckOption("뒤에서부터 세기", rule.fromEnd) { onChange(rule.copy(fromEnd = it)) }
                }
                is RenameRule.Numbering -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NumberField("시작", rule.start, Modifier.weight(1f)) { onChange(rule.copy(start = it)) }
                        NumberField("증가", rule.step, Modifier.weight(1f)) { onChange(rule.copy(step = it)) }
                        NumberField("자릿수", rule.digits, Modifier.weight(1f)) { onChange(rule.copy(digits = it)) }
                    }
                    Field("구분 문자", rule.separator) { onChange(rule.copy(separator = it)) }
                    PositionChips(rule.position, allowIndex = false) { onChange(rule.copy(position = it)) }
                }
                is RenameRule.Template -> {
                    Field("새 이름 틀", rule.pattern) { onChange(rule.copy(pattern = it)) }
                    NumberField("{n} 시작 번호", rule.start) { onChange(rule.copy(start = it)) }
                    Hint("{name} 현재 이름 · {n} 번호 · {n:3} 3자리 번호 · {parent} 폴더 이름 · {date} 수정일\n예) {parent}_{n:3}")
                }
                is RenameRule.ChangeCase -> {
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        CaseMode.entries.forEach { m ->
                            FilterChip(selected = rule.mode == m, onClick = { onChange(rule.copy(mode = m)) }, label = { Text(m.label) })
                        }
                    }
                }
                is RenameRule.Overwrite -> {
                    Field("새 이름 (확장자 제외)", rule.newName) { onChange(rule.copy(newName = it)) }
                    Hint("여러 파일에 같은 이름을 쓰면 겹치므로 '뒤에 화수 붙이기'나 '번호 붙이기'와 함께 쓰세요")
                }
                is RenameRule.EpisodeSuffix -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NumberField("시작 번호", rule.start, Modifier.weight(1f)) { onChange(rule.copy(start = it)) }
                        NumberField("증가", rule.step, Modifier.weight(1f)) { onChange(rule.copy(step = it)) }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("화", "권").forEach { u ->
                            key(u) { FilterChip(selected = rule.unit == u, onClick = { onChange(rule.copy(unit = u)) }, label = { Text(u) }) }
                        }
                    }
                    Hint("이름 끝에 있던 'N화/N권'은 지우고 새 번호를 붙입니다 (적용 범위에 든 파일만 차례로)")
                }
                is RenameRule.Extension -> {
                    Field("새 확장자 (예: txt, 비우면 제거)", rule.newExt) { onChange(rule.copy(newExt = it)) }
                    Hint("'확장자까지 포함' 옵션이 꺼져 있을 때만 적용됩니다")
                }
            }
        }
    }
}

@Composable
private fun Field(label: String, value: String, mono: Boolean = false, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        singleLine = true,
        textStyle = if (mono) MaterialTheme.typography.bodyLarge.copy(fontFamily = FontFamily.Monospace) else MaterialTheme.typography.bodyLarge,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun NumberField(label: String, value: Int, modifier: Modifier = Modifier.fillMaxWidth(), onChange: (Int) -> Unit) {
    var text by remember { mutableStateOf(value.toString()) }
    OutlinedTextField(
        value = text,
        onValueChange = { t ->
            if (t.isEmpty() || t == "-" || t.toIntOrNull() != null) {
                text = t
                onChange(t.toIntOrNull() ?: 0)
            }
        },
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        modifier = modifier,
    )
}

@Composable
private fun CheckOption(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Checkbox(checked = checked, onCheckedChange = onChange)
        Text(label, modifier = Modifier.padding(end = 12.dp))
    }
}

@Composable
private fun PositionChips(current: TextPosition, allowIndex: Boolean, onChange: (TextPosition) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        TextPosition.entries.filter { allowIndex || it != TextPosition.INDEX }.forEach { p ->
            key(p) { FilterChip(selected = current == p, onClick = { onChange(p) }, label = { Text(p.label) }) }
        }
    }
}

@Composable
private fun Hint(text: String) {
    Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun PostSwitch(title: String, desc: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title)
            Text(desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}
