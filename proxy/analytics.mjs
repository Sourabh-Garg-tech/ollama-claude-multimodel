#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LOG_DIR = path.join(__dirname, '..', 'logs');

// Parse CLI args
const args = process.argv.slice(2);
const command = args[0] || 'summary';

let fromDate = null;
let toDate = null;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--from' && args[i + 1]) fromDate = args[++i];
  if (args[i] === '--to' && args[i + 1]) toDate = args[++i];
}

const today = new Date().toISOString().split('T')[0];
if (!fromDate) fromDate = today;
if (!toDate) toDate = today;

function loadLogs(from, to) {
  const entries = [];
  const start = new Date(from);
  const end = new Date(to);

  if (!fs.existsSync(LOG_DIR)) return entries;

  const files = fs.readdirSync(LOG_DIR).filter(f => f.endsWith('.jsonl')).sort();

  for (const file of files) {
    const dateStr = file.replace('.jsonl', '');
    const fileDate = new Date(dateStr);
    if (fileDate >= start && fileDate <= end) {
      const lines = fs.readFileSync(path.join(LOG_DIR, file), 'utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          entries.push(JSON.parse(line));
        } catch { /* skip malformed lines */ }
      }
    }
  }
  return entries;
}

function formatNumber(n) {
  return n.toLocaleString();
}

function printSummary(entries) {
  if (entries.length === 0) {
    console.log('No usage data found for the specified date range.');
    return;
  }

  const totalInput = entries.reduce((s, e) => s + (e.input_tokens || 0), 0);
  const totalOutput = entries.reduce((s, e) => s + (e.output_tokens || 0), 0);
  const totalDuration = entries.reduce((s, e) => s + (e.duration_ms || 0), 0);

  console.log(`=== Usage Summary: ${fromDate}${fromDate !== toDate ? ` to ${toDate}` : ''} ===\n`);
  console.log(`Requests:          ${formatNumber(entries.length)}`);
  console.log(`Total input tokens: ${formatNumber(totalInput)}`);
  console.log(`Total output tokens:${formatNumber(totalOutput)}`);
  console.log(`Total tokens:       ${formatNumber(totalInput + totalOutput)}`);
  console.log(`Avg duration:      ${Math.round(totalDuration / entries.length).toLocaleString()}ms`);
}

function printModels(entries) {
  if (entries.length === 0) {
    console.log('No usage data found for the specified date range.');
    return;
  }

  const byModel = {};
  for (const e of entries) {
    const m = e.model || 'unknown';
    if (!byModel[m]) byModel[m] = { count: 0, input: 0, output: 0 };
    byModel[m].count++;
    byModel[m].input += e.input_tokens || 0;
    byModel[m].output += e.output_tokens || 0;
  }

  const totalInput = entries.reduce((s, e) => s + (e.input_tokens || 0), 0);
  const totalOutput = entries.reduce((s, e) => s + (e.output_tokens || 0), 0);

  console.log(`=== Per-Model Breakdown: ${fromDate}${fromDate !== toDate ? ` to ${toDate}` : ''} ===\n`);
  console.log(`Total: ${formatNumber(entries.length)} requests, ${formatNumber(totalInput)} in / ${formatNumber(totalOutput)} out\n`);

  for (const [model, data] of Object.entries(byModel).sort((a, b) => b[1].count - a[1].count)) {
    const pct = ((data.count / entries.length) * 100).toFixed(1);
    console.log(`  ${model}`);
    console.log(`    ${formatNumber(data.count)} requests (${pct}%)`);
    console.log(`    ${formatNumber(data.input)} in / ${formatNumber(data.output)} out`);
    console.log();
  }
}

function printSessions(entries) {
  if (entries.length === 0) {
    console.log('No usage data found for the specified date range.');
    return;
  }

  const bySession = {};
  for (const e of entries) {
    const sid = e.session_id || 'no-session';
    if (!bySession[sid]) bySession[sid] = { count: 0, input: 0, output: 0, models: new Set() };
    bySession[sid].count++;
    bySession[sid].input += e.input_tokens || 0;
    bySession[sid].output += e.output_tokens || 0;
    if (e.model) bySession[sid].models.add(e.model);
  }

  const totalInput = entries.reduce((s, e) => s + (e.input_tokens || 0), 0);
  const totalOutput = entries.reduce((s, e) => s + (e.output_tokens || 0), 0);

  console.log(`=== Per-Session Breakdown: ${fromDate}${fromDate !== toDate ? ` to ${toDate}` : ''} ===\n`);
  console.log(`Total: ${formatNumber(entries.length)} requests, ${formatNumber(totalInput)} in / ${formatNumber(totalOutput)} out\n`);

  for (const [sid, data] of Object.entries(bySession).sort((a, b) => b[1].input - a[1].input)) {
    const pct = ((data.count / entries.length) * 100).toFixed(1);
    const models = [...data.models].join(', ');
    console.log(`  ${sid}`);
    console.log(`    ${formatNumber(data.count)} requests (${pct}%) | ${formatNumber(data.input)} in / ${formatNumber(data.output)} out`);
    console.log(`    Models: ${models}`);
    console.log();
  }
}

function printDaily(entries) {
  if (entries.length === 0) {
    console.log('No usage data found for the specified date range.');
    return;
  }

  const byDay = {};
  for (const e of entries) {
    const day = (e.timestamp || '').split('T')[0] || 'unknown';
    if (!byDay[day]) byDay[day] = { count: 0, input: 0, output: 0 };
    byDay[day].count++;
    byDay[day].input += e.input_tokens || 0;
    byDay[day].output += e.output_tokens || 0;
  }

  console.log(`=== Daily Totals: ${fromDate} to ${toDate} ===\n`);
  console.log('Date        | Requests | Input Tokens | Output Tokens | Total');
  console.log('------------|----------|-------------|--------------|-------');

  for (const [day, data] of Object.entries(byDay).sort()) {
    console.log(
      `${day}  | ${String(data.count).padStart(8)} | ${formatNumber(data.input).padStart(11)} | ${formatNumber(data.output).padStart(12)} | ${formatNumber(data.input + data.output)}`
    );
  }
}

function printRaw(entries) {
  for (const e of entries) {
    console.log(JSON.stringify(e));
  }
}

// Run command
const entries = loadLogs(fromDate, toDate);

switch (command) {
  case 'summary':
    printSummary(entries);
    break;
  case 'models':
    printModels(entries);
    break;
  case 'sessions':
    printSessions(entries);
    break;
  case 'daily':
    printDaily(entries);
    break;
  case 'raw':
    printRaw(entries);
    break;
  default:
    console.log(`Usage: node analytics.mjs [command] [--from DATE] [--to DATE]\n`);
    console.log('Commands:');
    console.log('  summary   Today\'s usage summary (default)');
    console.log('  models    Per-model breakdown');
    console.log('  sessions  Per-session breakdown (by instance ID)');
    console.log('  daily     Daily totals over a date range');
    console.log('  raw       Output raw JSONL entries');
    console.log('\nOptions:');
    console.log('  --from DATE   Start date (YYYY-MM-DD), defaults to today');
    console.log('  --to DATE     End date (YYYY-MM-DD), defaults to --from');
    process.exit(1);
}