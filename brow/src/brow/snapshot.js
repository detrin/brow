(arg) => {
    const opts = arg || {};
    const rootEl = opts.root || document.body;
    const searchMode = !!opts.search;

    document.querySelectorAll('[data-brow-ref]').forEach(el => el.removeAttribute('data-brow-ref'));

    const INTERACTIVE = new Set([
        'a', 'button', 'input', 'select', 'textarea', 'option',
        'details', 'summary', 'dialog', 'menu', 'menuitem',
    ]);
    const INTERACTIVE_ROLES = new Set([
        'button', 'tab', 'link', 'menuitem', 'option', 'switch',
        'checkbox', 'radio', 'slider', 'spinbutton', 'combobox',
        'searchbox', 'textbox',
    ]);
    const SEMANTIC = new Set([
        'h1','h2','h3','h4','h5','h6','img','video','audio',
        'table','thead','tbody','tr','th','td','ul','ol','li',
        'form','label','fieldset','legend','nav','main',
    ]);
    const SKIP = new Set([
        'script','style','noscript','svg','path','link','meta',
        'br','hr','iframe',
    ]);
    const CHROME = new Set(['nav', 'header', 'footer', 'aside']);
    const CHROME_ROLES = new Set(['navigation', 'banner', 'contentinfo', 'complementary']);

    function isInteractiveEl(el) {
        return INTERACTIVE.has(el.tagName.toLowerCase()) || INTERACTIVE_ROLES.has(el.getAttribute('role'));
    }

    // Pre-scan: count interactive elements to set adaptive cap
    const allElements = rootEl.querySelectorAll('*');
    let interactiveCount = 0;
    for (const el of allElements) {
        if (isInteractiveEl(el)) interactiveCount++;
    }

    // The budget spends text nodes as well as elements, so the denominator in
    // "N of M nodes" has to count them too — otherwise the notice can claim
    // more nodes were kept than the page has.
    let totalNodes = allElements.length;
    try {
        const walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            if (walker.currentNode.textContent && walker.currentNode.textContent.trim()) totalNodes++;
        }
    } catch (e) { /* denominator stays element-only */ }

    let NODE_LIMIT;
    if (interactiveCount < 50) {
        NODE_LIMIT = 200;
    } else if (interactiveCount <= 150) {
        NODE_LIMIT = 400;
    } else {
        NODE_LIMIT = 300;
    }

    // Under --search only matching lines reach the caller, so a stingy walk buys
    // no tokens and costs matches that silently never existed. Walk wide instead.
    if (searchMode) NODE_LIMIT = 8000;
    const TEXT_MAX = searchMode ? 400 : 80;
    const CELL_MAX = searchMode ? 400 : 60;
    const MAX_TABLE_ROWS = searchMode ? 500 : 10;

    // Smallest budget the chrome pass may be left with, so the page's controls
    // survive even when the content pass spends everything.
    // (Also keeps the pass-2 cap above zero: a zero cap would make buildTree
    // bail at the root and take the spliced content subtree down with it.)
    const CHROME_FLOOR = 60;

    // Nodes a menu-like container may spend when it sits inside the content root.
    const MENU_QUOTA = 12;

    // One budget, re-capped per pass. `capped` records a container quota firing,
    // `exhausted` a pass running out — both mean nodes were dropped.
    const budget = { spent: 0, cap: NODE_LIMIT, exhausted: false, capped: false };
    function out() { return budget.spent >= budget.cap; }

    const refEls = [];
    let walkErrors = 0;
    let walkError = '';
    const skipNonInteractive = interactiveCount > 150;

    function isVisible(el) {
        if (!el || el.hidden || el.getAttribute('aria-hidden') === 'true') return false;
        return el.offsetParent !== null || el.getClientRects().length > 0;
    }

    // Collapse runs of whitespace before measuring. Raw textContent counts the
    // newlines and indentation between elements, which on a 842-item dropdown
    // adds up to more "prose" than a real article has — enough to make a menu
    // outscore the content it sits next to.
    function textLen(el) {
        return (el.textContent || '').replace(/\s+/g, ' ').trim().length;
    }

    // Prose, not link text: a 140-link navbar is bigger than the article it sits
    // above, so counting characters alone picks the chrome every time.
    function scoreBlock(el) {
        const text = textLen(el);
        if (!text) return 0;
        let linkText = 0;
        for (const a of el.querySelectorAll('a')) linkText += textLen(a);
        const fields = el.querySelectorAll('input, select, textarea').length;
        return Math.max(0, text - linkText) + fields * 30;
    }

    // A big container carrying no prose of its own is a menu, not content, even
    // when it sits inside <main> — github.com/trending keeps a 1,000-entry
    // language dropdown there, and uncapped it spends the entire content budget
    // before the repository rows are reached. A listing earns its budget by
    // carrying real text per row; a dropdown of bare links does not.
    function looksLikeMenu(el) {
        const role = el.getAttribute('role');
        if (role === 'menu' || role === 'listbox' || role === 'tablist') return true;
        return scoreBlock(el) < el.children.length * 20;
    }

    function findContentRoot() {
        if (rootEl !== document.body) return null;  // already scoped by --locator

        const main = document.querySelector('main, [role="main"]');
        if (main && main !== document.body && isVisible(main)) return main;

        const articles = Array.from(document.querySelectorAll('article'));
        if (articles.length === 1 && isVisible(articles[0])) return articles[0];
        if (articles.length > 1) {
            // A page of article cards: the list container is the content, not the
            // first card.
            const parent = articles[0].parentElement;
            if (parent && parent !== document.body &&
                articles.every(a => a.parentElement === parent) && isVisible(parent)) {
                return parent;
            }
        }

        const CANDIDATE = new Set(['div', 'section', 'table', 'ul', 'ol']);
        let best = null;
        let bestScore = 200;  // floor: below this there is no content worth reserving for
        let examined = 0;

        function scan(node, depth) {
            if (depth > 6 || examined > 400) return;
            for (const child of node.children) {
                const tag = child.tagName.toLowerCase();
                if (SKIP.has(tag) || CHROME.has(tag)) continue;
                if (CHROME_ROLES.has(child.getAttribute('role'))) continue;
                if (CANDIDATE.has(tag) && isVisible(child)) {
                    examined++;
                    // >= so a tighter descendant with the same substance wins.
                    const score = scoreBlock(child);
                    if (score >= bestScore) { bestScore = score; best = child; }
                }
                scan(child, depth + 1);
            }
        }
        scan(document.body, 0);
        return best;
    }

    function describe(el) {
        const tag = el.tagName.toLowerCase();
        if (el.id) return tag + '#' + el.id;
        const cls = typeof el.className === 'string' ? el.className.trim().split(/\s+/)[0] : '';
        return cls ? tag + '.' + cls : tag;
    }

    function sig(node) {
        if (node.nodeType !== Node.ELEMENT_NODE) return '';
        // On SVG elements className is an SVGAnimatedString, not a string, so
        // .split() throws. sig() runs outside the child loop's try, so that
        // throw used to escape buildTree and get swallowed by the *parent's*
        // catch — silently deleting every icon-bearing link and button from the
        // snapshot. That, not the node budget, is why github.com/trending
        // showed zero repository rows.
        const raw = typeof node.className === 'string' ? node.className : '';
        const cls = raw ? '.' + raw.split(' ')[0] : '';
        const ch = node.children.length;
        return node.tagName + cls + ch;
    }

    let contentRoot = null;
    let contentTree = null;
    let contentDone = false;
    let contentSpliced = false;
    let inContentPass = false;

    // Ancestors of the content root, until it has been spliced in. Pass 2 must
    // stay able to walk down to the content subtree even with an exhausted
    // budget, or a heavy header makes it discard the very content pass 1 spent
    // the whole budget building — which is what left github.com/trending and
    // Wikipedia articles with nothing but chrome.
    function onContentPath(node) {
        if (!contentDone || contentSpliced || !contentRoot) return false;
        if (!node || node.nodeType !== Node.ELEMENT_NODE) return false;
        return node === contentRoot || node.contains(contentRoot);
    }

    function buildTree(node, depth) {
        if (!node || depth > 15) return null;

        // The content subtree is already paid for; splice it in at its document
        // position so the output order is exactly what it was before. Checked
        // before the budget, because reaching it must never depend on what pass
        // 2 has left over.
        if (contentDone && node === contentRoot) {
            contentSpliced = true;
            return contentTree;
        }
        if (out() && !onContentPath(node)) return null;

        if (node.nodeType === Node.TEXT_NODE) {
            const t = node.textContent?.trim();
            if (!t || !t.length) return null;
            budget.spent++;
            return { role: 'text', name: t.substring(0, TEXT_MAX) };
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return null;

        const tag = node.tagName.toLowerCase();
        if (SKIP.has(tag)) return null;

        // Table-aware: emit compact table node instead of deep tree
        if (tag === 'table') {
            budget.spent++;
            const headers = [];
            const rows = [];
            const ths = node.querySelectorAll('thead th, thead td, tr:first-child th');
            ths.forEach(th => headers.push(th.textContent?.trim()?.substring(0, CELL_MAX) || ''));
            const trs = node.querySelectorAll('tbody tr, tr');
            const startIdx = headers.length > 0 && trs.length > 0 && trs[0].querySelector('th') ? 1 : 0;
            for (let i = startIdx; i < trs.length && rows.length < MAX_TABLE_ROWS; i++) {
                const cells = [];
                trs[i].querySelectorAll('td, th').forEach(td => {
                    cells.push(td.textContent?.trim()?.substring(0, CELL_MAX) || '');
                });
                if (cells.length > 0) rows.push(cells);
            }
            const totalRows = trs.length - startIdx;
            return { role: 'table', headers, rows, totalRows };
        }

        if (node.hidden || node.getAttribute('aria-hidden') === 'true') return null;

        const role = node.getAttribute('role') || tag;
        const ariaLabel = node.getAttribute('aria-label');
        const alt = node.getAttribute('alt');
        const placeholder = node.getAttribute('placeholder');
        const name = ariaLabel || alt || node.getAttribute('title') || '';
        const isInteractive = INTERACTIVE.has(tag) || INTERACTIVE_ROLES.has(node.getAttribute('role'));
        const isSemantic = SEMANTIC.has(tag);

        const childNodes = Array.from(node.childNodes);
        // A single 180-item dropdown must not be able to spend the whole pass.
        // Only genuinely huge containers are capped, so listings of a dozen
        // varied cards are left alone; the pass root is exempt, since there is
        // nothing else in the pass for it to crowd out, and so are the content
        // root's ancestors, since capping one could cut the walk off before it
        // reached the spliced subtree.
        // Search mode caps nothing: only matching lines reach the caller, so a
        // quota buys no tokens and costs matches — a language buried in a
        // 842-item dropdown has to be findable.
        let quota = 0;
        if (!searchMode && depth > 0 && node.children.length > 20 && !onContentPath(node)) {
            if (!inContentPass) {
                quota = Math.max(20, Math.floor(budget.cap * 0.2));
            } else if (looksLikeMenu(node)) {
                // Inside the content root, a menu gets a flat allowance rather
                // than a share of the budget: three dropdowns in <main> at 20%
                // each is 60% of the content budget spent on things that are not
                // content. This keeps a few refs and the omitted-item count.
                quota = MENU_QUOTA;
            }
        }
        const spentBefore = budget.spent;
        let children = [];
        let lastSig = '', repeatCount = 0;
        let seen = 0;
        for (const child of childNodes) {
            if (out() && !onContentPath(child)) {
                // Out of budget: stop, unless the content subtree is still
                // waiting further along this child list.
                if (!onContentPath(node)) break;
                continue;
            }
            if (quota && budget.spent - spentBefore >= quota) {
                const left = node.children.length - seen;
                if (left > 0) {
                    children.push({ role: 'text', name: '... ' + left + ' more items omitted (container cap)' });
                    budget.spent++;
                    budget.capped = true;
                }
                break;
            }
            if (child.nodeType === Node.ELEMENT_NODE) seen++;
            const s = sig(child);
            if (s && s === lastSig) {
                repeatCount++;
                if (repeatCount > 3) continue;
            } else {
                if (repeatCount > 3) {
                    children.push({ role: 'text', name: '... ' + (repeatCount - 3) + ' similar items omitted' });
                    budget.spent++;
                }
                lastSig = s;
                repeatCount = 0;
            }
            try {
                const c = buildTree(child, depth + 1);
                if (c) children.push(c);
            } catch (e) {
                // Dropping a subtree silently is how a one-line crash hid real
                // page content for as long as it did. Count it and report it.
                walkErrors++;
                if (!walkError) walkError = e.message;
            }
        }
        if (repeatCount > 3) {
            children.push({ role: 'text', name: '... ' + (repeatCount - 3) + ' similar items omitted' });
            budget.spent++;
        }

        if (!isInteractive && !isSemantic && !name) {
            if (children.length === 0) return null;
            if (children.length === 1) return children[0];
            return { role: 'group', children };
        }

        // When interactive-dense, skip non-interactive non-semantic nodes sooner.
        // Never during the content pass: on a link-dense article (a wiki page,
        // say) "non-interactive" is the prose, and dropping it defeats the
        // reason the content pass exists.
        if (skipNonInteractive && !inContentPass && !isInteractive && budget.spent > budget.cap * 0.7) {
            if (children.length === 0) return null;
            return { role: 'group', children };
        }

        budget.spent++;
        const obj = { role };
        if (isInteractive) {
            // Provisional number; renumber() below reassigns refs in output
            // order and writes the DOM attributes to match.
            refEls.push(node);
            obj.ref = refEls.length;
        }
        if (name) obj.name = name.substring(0, TEXT_MAX);
        else if (isInteractive && !name) {
            const txt = node.textContent?.trim()?.substring(0, 50);
            if (txt) obj.name = txt;
        }
        if (placeholder && !obj.name) obj.name = placeholder;
        const inputType = tag === 'input' ? (node.getAttribute('type') || 'text').toLowerCase() : '';
        if (inputType !== 'password' && node.value !== undefined && node.value !== '') {
            obj.value = String(node.value).substring(0, 80);
        }
        if (node.checked !== undefined) obj.checked = node.checked;
        if (node.disabled) obj.disabled = true;
        if (tag === 'a' && node.href) obj.href = node.href;

        if (children.length > 0) {
            if (children.length === 1 && children[0].role === 'text' && !obj.name) {
                obj.name = children[0].name;
            } else {
                obj.children = children;
            }
        }

        // List compression: inline >5 same-type simple children
        if (children.length > 5) {
            const roles = children.map(c => c.role);
            const firstRole = roles[0];
            const allSame = roles.every(r => r === firstRole);
            const allSimple = children.every(c => !c.children || c.children.every(gc => gc.role === 'text'));
            if (allSame && allSimple) {
                return { role: 'inline-list', itemRole: firstRole, items: children };
            }
        }

        return obj;
    }

    // Two passes build the content subtree before the chrome around it, so refs
    // are assigned out of document order. Renumber the assembled tree so [N]
    // still ascends as the caller reads down it, and point the DOM attributes at
    // the new numbers. Refs on subtrees that were built but dropped never make
    // it here, so no stale attribute is left behind for a click to resolve.
    function renumber(tree) {
        const assigned = [];
        function visit(node) {
            if (!node || typeof node !== 'object') return;
            if (node.ref !== undefined) {
                assigned.push(refEls[node.ref - 1]);
                node.ref = assigned.length;
            }
            (node.items || []).forEach(visit);
            (node.children || []).forEach(visit);
        }
        visit(tree);
        document.querySelectorAll('[data-brow-ref]').forEach(el => el.removeAttribute('data-brow-ref'));
        assigned.forEach((el, i) => { if (el) el.setAttribute('data-brow-ref', String(i + 1)); });
        return assigned.length;
    }

    function safeBuild(node) {
        try {
            return buildTree(node, 0);
        } catch (e) {
            // Fallback: return minimal tree on crash
            return { role: 'text', name: 'Snapshot error: ' + e.message };
        }
    }

    let contentDescriptor = null;
    let contentComplete = true;
    let contentSpent = 0;
    try {
        contentRoot = findContentRoot();
    } catch (e) {
        contentRoot = null;
    }

    // Pass 1: the content root is walked first and may spend the entire budget.
    // Capping it below NODE_LIMIT would make content *worse* off than the old
    // single pass on any page whose content came first, which is exactly what a
    // long article is.
    if (contentRoot) {
        contentDescriptor = describe(contentRoot);
        budget.cap = NODE_LIMIT;
        budget.spent = 0;
        inContentPass = true;
        contentTree = safeBuild(contentRoot);
        inContentPass = false;
        contentComplete = !out();
        if (!contentComplete) budget.exhausted = true;
        contentDone = true;
        contentSpent = budget.spent;
        // Chrome gets the remainder, but never nothing: a snapshot with no nav
        // or search refs at all cannot be acted on, and CHROME_FLOOR nodes is
        // cheap next to losing the page's controls.
        budget.cap = Math.max(CHROME_FLOOR, NODE_LIMIT - contentSpent);
        budget.spent = 0;
    }

    // Pass 2: everything else, in document order, with the content spliced back in.
    const tree = safeBuild(rootEl);
    if (out()) budget.exhausted = true;

    return {
        tree,
        truncated: budget.exhausted || budget.capped,
        nodeCount: contentSpent + budget.spent,
        totalNodes,
        contentRoot: contentDescriptor,
        contentComplete,
        refCount: renumber(tree),
        interactiveCount,
        walkErrors,
        walkError,
    };
}
