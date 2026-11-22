/* Generate distributable docs from the same content used by /guide. No secrets or DB access. */
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const guide = JSON.parse(fs.readFileSync(path.join(root, 'frontend/src/content/user-guide.ar.json'), 'utf8'));
const lines = [`# ${guide.title}`, '', guide.subtitle, '', `**الإصدار ${guide.version}**`, '', guide.scope, '', '## فهرس الدليل', ''];
guide.sections.forEach((section, index) => lines.push(`${index + 1}. ${section.title} — ${section.audience}`));
guide.sections.forEach((section, index) => {
  lines.push('', `## ${index + 1}. ${section.title}`, '', `**${section.audience}**`, '');
  if (section.intro) lines.push(section.intro, '');
  (section.steps || []).forEach((step, i) => lines.push(`${i + 1}. ${step}`));
  if (section.table) {
    lines.push('', `| ${section.table.headers.join(' | ')} |`, `| ${section.table.headers.map(() => '---').join(' | ')} |`);
    section.table.rows.forEach(row => lines.push(`| ${row.join(' | ')} |`));
  }
  (section.notes || []).forEach(note => lines.push('', `> ${note}`));
  (section.questions || []).forEach(item => lines.push('', `### ${item.question}`, '', item.answer));
  if (section.links?.length) lines.push('', '**أين أجد ذلك؟**', ...section.links.map(link => `- ${link.label}: ${link.to}`));
});
lines.push('', '---', '', 'هذا الدليل لا يحتوي بيانات دخول أو روابط تفعيل خاصة أو بيانات تحويل مالية. اعتمد تعليمات الدفع الظاهرة في عمليتك، وتواصل مع إدارة المركز عند الحاجة.', '');
const markdown = lines.join('\n');
for (const target of ['docs/USER_GUIDE_AR.md', 'frontend/public/docs/kura-user-guide-ar.md']) {
  const file = path.join(root, target);
  fs.mkdirSync(path.dirname(file), {recursive: true});
  fs.writeFileSync(file, markdown, 'utf8');
}
console.log(`User guide generated: ${guide.sections.length} chapters; source and download copies match.`);