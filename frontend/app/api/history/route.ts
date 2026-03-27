import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    // Process cwd is frontend directory
    const logPath = path.join(process.cwd(), '../data/fitness-log.md');
    const content = fs.readFileSync(logPath, 'utf8');

    const sections = content.split('## ').slice(1); // skip the title block
    const days = sections.filter(s => s.trim().startsWith('Day'));
    const history = days.map(dayText => {
      const lines = dayText.trim().split('\n');
      const title = lines[0].split('-').pop()?.trim() || 'Unknown Day';
      
      const text = lines.slice(1).join(' ');
      
      const stepsMatch = text.match(/Steps:\s*([\d,]+)/i);
      const calsMatch = text.match(/Calories:\s*([\d,]+)/i);
      const proteinMatch = text.match(/Protein:\s*([\d,]+)/i);
      
      return {
        name: title,
        steps: stepsMatch ? parseInt(stepsMatch[1].replace(/,/g, '')) : 0,
        calories: calsMatch ? parseInt(calsMatch[1].replace(/,/g, '')) : 0,
        protein: proteinMatch ? parseInt(proteinMatch[1].replace(/,/g, '')) : 0,
      };
    }).filter(d => d.steps > 0 || d.calories > 0 || d.protein > 0);

    return NextResponse.json(history);
  } catch (error) {
    console.error("Error reading history:", error);
    return NextResponse.json({ error: "Failed to read history" }, { status: 500 });
  }
}
