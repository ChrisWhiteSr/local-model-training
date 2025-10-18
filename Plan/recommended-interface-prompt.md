# Interface Design Brief: Local RAG System Redesign

## System Overview

You are tasked with redesigning the user interface for a **Local RAG (Retrieval-Augmented Generation) System** that allows users to:
1. Ingest PDF documents into a vector database
2. Query those documents using natural language
3. Receive AI-generated answers with source citations
4. Monitor ingestion progress in real-time
5. Manage their document library

**Current Tech Stack:**
- Frontend: React + TypeScript + Vite
- UI Library: Mantine (must be retained)
- Backend: FastAPI (provides REST + SSE endpoints)
- Data Flow: Real-time SSE with fallback polling

---

## Core Functionality Requirements

### 1. Document Ingestion Module
**Purpose**: Allow users to ingest PDF files into the vector database

**Features to Support:**
- **Trigger ingestion** of all PDFs in a directory
- **Force re-ingest** to bypass checksum cache (testing/debugging)
- **Real-time progress display**:
  - Files found (e.g., "7 PDFs detected")
  - Current file being processed
  - Pages processed / total pages
  - Chunks created and stored
  - Files skipped (unchanged since last ingest)
- **Live event stream** showing:
  - File start/completion events
  - OCR events when applied to image-heavy pages
  - Errors with clear messaging
- **Final summary card**:
  - Total files found/processed/skipped
  - Total pages processed
  - Total chunks stored in vector database
  - List of successfully processed files
  - List of skipped files (with reason)
  - List of failed files (with error details)

**Current Pain Points:**
- Minimal visual feedback during long-running operations
- Summary data presented as plain text with no visual hierarchy
- No progress bar or percentage indicator
- Errors buried in logs rather than surfaced prominently
- No indication of system health (SSE vs. polling fallback)

---

### 2. Query/Search Module
**Purpose**: Allow users to query their document collection with natural language

**Features to Support:**
- **Text input** for natural language questions
- **Configurable parameters**:
  - Top-K: Number of chunks to retrieve (default 8)
  - Similarity threshold: Minimum relevance score
- **Query execution** with loading state
- **Response display**:
  - AI-generated answer (from LLM)
  - Source citations showing:
    - Document name
    - Page number
    - Relevance score (optional)
    - Snippet preview of matched chunk
- **Query history** (future enhancement)
- **Latency display** (queries take 15-20 seconds on local model)

**Current Pain Points:**
- Basic text input with no visual polish
- Citations displayed as raw JSON-like data
- No visual separation between answer and sources
- No indication of retrieval quality (relevance scores)
- No way to navigate to source documents
- Long wait times (18+ seconds) with minimal feedback

---

### 3. Document Library Module
**Purpose**: View and manage ingested documents

**Features to Support:**
- **List of all documents** in the vector database
- **Document metadata**:
  - File name
  - Pages count
  - Chunks count
  - Ingestion date/checksum
  - OCR events applied (if any)
- **View document details** (future: preview PDFs)
- **Delete documents** from vector store (future)
- **Re-ingest specific document** (currently available via force flag)

**Current Pain Points:**
- Currently shows raw `/documents` endpoint response
- No visual cards or grid layout
- No way to interact with individual documents
- No search/filter capability

---

### 4. System Status Module
**Purpose**: Show system health and connection status

**Features to Support:**
- **Backend connection status** (connected/disconnected)
- **Event stream status** (SSE active / Fallback polling)
- **LM Studio status** (embeddings + chat model)
- **ChromaDB status** (vector count, collection info)
- **Recent errors/warnings** (last 5-10 events)

**Current Pain Points:**
- Connection status shown as plain text badge
- No visual indicator of system health
- No consolidated error log visible to user
- Users must check terminal logs for debugging

---

## User Personas

### Primary: Research Analyst
- **Goals**: Quickly extract insights from large document collections
- **Needs**: Fast queries, accurate citations, ability to verify sources
- **Technical Skill**: Medium (comfortable with web UIs, not command line)
- **Use Case**: Ingests 50+ PDF reports, queries for market trends, exports findings

### Secondary: Developer/Tester
- **Goals**: Test the RAG pipeline, debug ingestion issues, optimize retrieval
- **Needs**: Detailed logs, force re-ingest, configurable parameters, error visibility
- **Technical Skill**: High (can read logs, understands vector embeddings)
- **Use Case**: Iterates on chunk size, tests different embedding models, validates citations

### Tertiary: Business User
- **Goals**: Ask questions, get answers, trust the system
- **Needs**: Simple interface, clear citations, no technical jargon
- **Technical Skill**: Low (expects consumer-grade UX)
- **Use Case**: Asks "What did the Bain report say about healthcare M&A?"

---

## Key User Journeys

### Journey 1: First-Time Ingestion
1. User lands on application
2. Sees empty document library
3. Clicks "Ingest Documents" button
4. Sees real-time progress as 7 PDFs are processed
5. Views summary: "6 files, 234 pages, 581 chunks stored"
6. Sees document library populated with 6 entries
7. **Success Criteria**: User feels confident that ingestion worked

### Journey 2: Querying Documents
1. User types question: "What is Scientific Advertising about?"
2. Clicks "Search" or presses Enter
3. Sees loading indicator (with estimated time remaining)
4. Views AI-generated answer
5. Scrolls to citations section
6. Clicks on a citation to see the chunk preview
7. (Future) Clicks "View PDF" to open source document at correct page
8. **Success Criteria**: User trusts the answer because citations are clear

### Journey 3: Debugging Failed Ingestion
1. User triggers ingestion
2. Sees progress, then error appears on one file
3. Clicks error to expand details
4. Sees "Good-to-Great.pdf failed: ChromaDB metadata error"
5. Clicks "View Logs" to see full stack trace
6. Decides to skip that file and continue
7. **Success Criteria**: User understands what failed and why

### Journey 4: Re-Ingesting After Config Change
1. User modified PDF (added annotations)
2. Clicks "Force Re-Ingest All"
3. Sees confirmation modal: "This will bypass checksums and reprocess all files"
4. Confirms action
5. Watches progress bar as files are reprocessed
6. Sees updated summary with new chunk counts
7. **Success Criteria**: User can confidently trigger full refresh

---

## Design Constraints

### Technical Constraints
- **Must use Mantine UI library** (already integrated)
- **Must support Server-Sent Events** (SSE) for real-time updates
- **Must gracefully degrade** to polling if SSE fails
- **Must work on localhost** (no cloud deployment assumed)
- **Must handle 15-20 second query latency** gracefully

### Accessibility Constraints
- **WCAG 2.1 AA compliance** minimum
- **Keyboard navigation** for all interactive elements
- **Screen reader support** for status updates
- **High contrast mode** compatibility
- **No reliance on color alone** for status (use icons + text)

### Performance Constraints
- **Real-time updates** during ingestion (event every 0.5-2 seconds)
- **Long-running operations** (ingestion can take 5+ minutes for large collections)
- **Large data sets** (future: 1000+ documents, 50k+ chunks)
- **Responsive on mid-range hardware** (targeting local dev machines)

---

## Current Interface Architecture

### Existing Components
```
App.tsx
├── Documents Component
│   ├── Ingest All button
│   ├── Force Re-Ingest button
│   ├── Connection status badge
│   ├── Last ingest summary card
│   └── Document list (raw JSON display)
├── Query Component
│   ├── Text input
│   ├── Top-K slider
│   ├── Search button
│   └── Results display (basic text)
└── Event Stream (SSE + fallback polling)
```

### Key State Management
- `isIngesting`: Boolean flag
- `lastIngest`: Ingest summary object
- `polledLogs`: Array of recent events
- `documents`: Array from `/documents` endpoint

---

## Design Deliverables Requested

### 1. Information Architecture
- **Propose page structure**: Single-page vs. multi-page layout
- **Navigation pattern**: Tabs, sidebar, breadcrumbs, or other
- **Component hierarchy**: How should modules be organized?
- **Suggested routing** (if multi-page): `/ingest`, `/query`, `/library`, `/settings`

### 2. Visual Design System
- **Color palette**: Primary, secondary, success, error, warning states
- **Typography scale**: Headings, body, code, monospace for logs
- **Spacing system**: Consistent padding/margins
- **Component variants**: Button styles, card layouts, badge types
- **Icon set**: Recommended icons for actions and status
- **Mantine theme customization**: Specific overrides to default theme

### 3. Component Specifications

#### Ingestion Progress Component
- How should real-time events be displayed? (Timeline, feed, cards?)
- How to show file-level progress? (List, accordion, tabs?)
- Where to place summary stats? (Header, sidebar, modal?)
- How to handle errors? (Inline, toast, dedicated error panel?)

#### Query Results Component
- How should AI answer be styled? (Card, chat bubble, prose?)
- How should citations be presented? (List, grid, inline links?)
- How to show chunk previews? (Expandable, modal, sidebar?)
- How to indicate relevance? (Score badge, visual ranking, confidence meter?)

#### Document Library Component
- What layout for document cards? (Grid, list, table?)
- What metadata to show? (File size, date, page count, chunk count?)
- How to enable actions? (Hover menu, context menu, inline buttons?)

#### System Status Component
- Where to place status? (Header, footer, dedicated panel?)
- How to show connection health? (Pulse dot, status bar, dashboard widget?)
- How to surface recent errors? (Notification bell, inline alerts, console panel?)

### 4. Interaction Patterns
- **Loading states**: Skeleton screens, spinners, progress bars, or animated placeholders?
- **Empty states**: What to show when library is empty? When query returns no results?
- **Error states**: Toast notifications, inline alerts, or dedicated error page?
- **Success feedback**: Toasts, animations, or subtle state changes?
- **Long-running operations**: Dismissible progress modals, pinned header bar, or background task tray?

### 5. Responsive Behavior
- **Desktop-first** (primary use case is localhost development)
- **Minimum viewport**: 1280x720
- **Preferred viewport**: 1920x1080
- **Mobile support**: Nice-to-have, not required

---

## Specific Design Questions to Answer

### Priority 1: Ingestion UX
1. **How should we visualize real-time progress** when ingesting 50+ files?
   - Option A: Single progress bar with "File 23/50" counter
   - Option B: Live event feed showing each file as it completes
   - Option C: Dashboard with multiple metrics updating simultaneously
   - Your recommendation: ___

2. **Where should the Force Re-Ingest button live?**
   - With normal Ingest button (current approach)
   - In a settings/advanced menu
   - In a confirmation modal after clicking Ingest
   - Your recommendation: ___

3. **How should we handle the SSE fallback polling state?**
   - Visible badge: "Using fallback polling"
   - Subtle icon change (green = SSE, yellow = polling)
   - Hidden from user entirely (they don't need to know)
   - Your recommendation: ___

### Priority 2: Query UX
4. **How should we display the 15-20 second wait time during queries?**
   - Progress bar with "Retrieving chunks... Generating answer..."
   - Animated skeleton of the results area
   - Playful loading animation with tips/facts
   - Your recommendation: ___

5. **How should citations be integrated with the answer?**
   - Footnote-style superscript numbers in answer text
   - Separate "Sources" section below answer
   - Sidebar with expandable source cards
   - Your recommendation: ___

6. **Should we show the retrieved chunks to the user?**
   - Yes, always visible (helps validate relevance)
   - Yes, but collapsed by default (click to expand)
   - No, only show summary citations (cleaner UX)
   - Your recommendation: ___

### Priority 3: Document Library
7. **What's the best way to show 100+ documents?**
   - Infinite scroll list
   - Paginated table with sorting
   - Grid of cards with search/filter
   - Your recommendation: ___

8. **Should we show chunk previews in the library view?**
   - Yes, show first chunk as preview
   - No, only metadata (file name, page count, etc.)
   - Show on hover/click
   - Your recommendation: ___

---

## Inspiration & References

### Similar Interfaces to Consider
- **ChatGPT**: Citation bubbles, clean chat interface, loading states
- **Perplexity AI**: Inline citations, source cards, streaming responses
- **Notion AI**: Embedded Q&A, subtle loading, inline results
- **GitHub Copilot**: Suggestion cards, accept/reject flows, confidence indicators
- **Algolia DocSearch**: Instant search, result previews, keyboard shortcuts

### RAG-Specific UX Patterns
- **Source credibility indicators**: Show which documents are most authoritative
- **Chunk context**: Show surrounding text to validate relevance
- **Multi-hop reasoning**: Visual indication when answer synthesizes multiple sources
- **Confidence scoring**: Show retrieval quality (e.g., "8 highly relevant chunks found")
- **Feedback loops**: Allow users to mark good/bad answers (future enhancement)

---

## Success Metrics

### Usability Goals
- [ ] User can trigger ingestion and understand progress **without reading logs**
- [ ] User can identify failed files and understand why **within 5 seconds**
- [ ] User can interpret query results and trust citations **without technical knowledge**
- [ ] User can navigate all core features **using keyboard only**
- [ ] User can understand system health (connected, processing, idle) **at a glance**

### Technical Goals
- [ ] UI remains responsive during 5+ minute ingestion operations
- [ ] Real-time events render without flicker or jank
- [ ] Layout adapts gracefully from 1280px to 2560px wide
- [ ] No color-only indicators (accessible to colorblind users)
- [ ] All interactive elements have visible focus states

---

## Constraints & Guardrails

### What NOT to Change
- **Mantine UI library**: Must continue using (no Material-UI, Chakra, etc.)
- **SSE + polling architecture**: Backend already built, frontend must adapt
- **React + TypeScript**: No framework changes
- **Localhost-first**: No assumption of cloud hosting or authentication

### What CAN Change
- **Layout structure**: Single-page, multi-page, dashboard, wizard—all options open
- **Color scheme**: Current default theme can be fully customized
- **Component organization**: Refactor as needed for better UX
- **State management**: Add Zustand, Redux, or other if beneficial
- **Routing**: Add React Router if multi-page layout is recommended

---

## Output Format

Please provide:

### 1. Executive Summary (1 page)
- Recommended layout approach (single-page dashboard, multi-page app, etc.)
- Top 3 UX improvements with biggest impact
- Key design principles for this specific RAG use case

### 2. Information Architecture (1 page)
- Sitemap or navigation structure
- Component hierarchy diagram
- User flow diagrams for key journeys

### 3. Visual Design System (2-3 pages)
- Color palette with semantic meaning (primary, error, warning, etc.)
- Typography scale and usage guidelines
- Mantine theme customization code snippet
- Icon recommendations (from Tabler Icons, Mantine's default)

### 4. Component Mockups (5-10 pages)
- **Ingestion Progress Component**: Wireframe + detailed spec
- **Query Results Component**: Wireframe + detailed spec
- **Document Library Component**: Wireframe + detailed spec
- **System Status Component**: Wireframe + detailed spec
- **Empty States**: For library, query, errors

### 5. Interaction Patterns (1-2 pages)
- Loading state strategy across all components
- Error handling patterns (toast vs. inline vs. modal)
- Success feedback approach
- Keyboard shortcuts (if recommended)

### 6. Implementation Guidance (1 page)
- Recommended Mantine components to use
- Suggested third-party libraries (charts, animations, etc.)
- Accessibility checklist specific to this design
- Phased implementation plan (MVP → Full feature set)

---

## Context: Why This Redesign Matters

### The Problem This System Solves
Users need to **query large collections of PDF documents** (research papers, business reports, technical manuals) using natural language instead of keyword search. The RAG system:
1. Breaks PDFs into searchable chunks
2. Finds the most relevant chunks for a query
3. Feeds those chunks to an LLM for a synthesized answer
4. Provides citations so users can verify sources

### Why UX Is Critical for RAG
- **Trust**: Users must trust AI-generated answers (citations are key)
- **Transparency**: Users need to see *why* the system gave this answer (show retrieved chunks)
- **Latency**: 15-20 second queries feel slow—need excellent loading UX
- **Feedback**: Ingestion is a black box without real-time progress
- **Debugging**: When retrieval fails, users need clear error messages

### Current State vs. Desired State

**Current**: Functional but minimal
- Plain buttons and text inputs
- Raw JSON-like data display
- Hidden errors (logs only)
- Unclear system status

**Desired**: Polished and trustworthy
- Professional dashboard feel
- Clear visual hierarchy
- Prominent citations and sources
- Real-time feedback everywhere
- Accessible to non-technical users

---

## Final Notes

This is a **localhost development tool** that will be used daily by:
- Researchers analyzing document collections
- Developers testing RAG pipelines
- Analysts extracting insights from reports

The interface should feel:
- **Professional** (not amateurish)
- **Informative** (show what's happening)
- **Trustworthy** (make citations obvious)
- **Efficient** (optimize for power users)

You have full creative freedom within the constraints listed above. Surprise us with thoughtful UX patterns that make RAG systems delightful to use.

---

**Thank you for taking on this design challenge! We're excited to see your recommendations.**
