#!/usr/bin/env node
/**
 * Send an HTML email via direct MX delivery using nodemailer.
 * Usage: node send_email.mjs <to> <subject> <html_file>
 */

import { createTransport } from "nodemailer";
import { execSync } from "child_process";
import { readFileSync } from "fs";

const [to, subject, htmlFile] = process.argv.slice(2);

if (!to || !subject || !htmlFile) {
  console.error("Usage: node send_email.mjs <to> <subject> <html_file>");
  process.exit(1);
}

// MX lookup
const domain = to.split("@")[1];
const mxRaw = execSync(`dig +short MX ${domain}`).toString().trim();
const mxLines = mxRaw
  .split("\n")
  .map((l) => l.trim().split(/\s+/))
  .filter((p) => p.length === 2)
  .map(([pri, host]) => ({ pri: parseInt(pri), host: host.replace(/\.$/, "") }))
  .sort((a, b) => a.pri - b.pri);

if (!mxLines.length) {
  console.error(`No MX records found for ${domain}`);
  process.exit(1);
}

const mxHost = mxLines[0].host;
console.log(`MX: ${mxHost}`);

const html = readFileSync(htmlFile, "utf-8");

const transporter = createTransport({
  host: mxHost,
  port: 25,
  secure: false,
  tls: { rejectUnauthorized: false },
  // Force IPv4 to avoid PTR record issues
  family: 4,
});

try {
  const info = await transporter.sendMail({
    from: "Competitor Monitor <competitor-monitor@claude-site.local>",
    to,
    subject,
    html,
  });
  console.log(`Email sent! Message ID: ${info.messageId}`);
  console.log(`Response: ${info.response}`);
} catch (err) {
  console.error(`Failed: ${err.message}`);
  process.exit(1);
}
