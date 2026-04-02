# Persona Studio Web (Next.js + TypeScript)

A frontend for:
- OpenAI / Anthropic compatible chat
- Real-time 3-layer memory display (L1/L2/L3)
- Persona cards + word cloud preview
- Persona export (JSON / SVG / PNG)

## 1) Install

```bash
cd web
npm install
```

## 2) Configure Provider Keys

```bash
cp .env.example .env.local
```

Fill keys in `.env.local`:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

If keys are empty, `/api/chat` returns mock text so UI remains testable.

## 3) Run

```bash
npm run dev
```

Open http://localhost:3000

## 4) Notes

- API route: `app/api/chat/route.ts`
- Main page: `app/page.tsx`
- Word cloud: `app/components/WordCloud.tsx`
