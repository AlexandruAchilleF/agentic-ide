// Date inventate pentru demo.
// În decembrie, datele astea vor veni de la OpenCode (prin SDK-ul lui),
// iar pagina rămâne la fel. Dacă vrei să schimbi un text, îl schimbi aici.

window.MOCK = {
  project: "demo-shop",
  agent: "Coder",
  prompt: "Testul test_total_with_discount pică. Găsește cauza și repar-o.",

  // Câte teste are proiectul de demo înainte de modificări.
  testsBase: 12,

  // Pașii agentului Coder, în ordinea în care apar pe ecran.
  // kind: "agent" (gândește), "tool" (cheamă o unealtă MCP), "edit" (modifică un fișier), "done" (a terminat)
  steps: [
    {
      kind: "agent",
      title: "Am primit cererea",
      detail: "Testul apelează funcția total_price. Încep cu ea.",
    },
    {
      kind: "tool",
      server: "context-engine",
      title: 'find_symbol("total_price")',
      detail: "Găsită în shop/cart.py, liniile 4–11.",
    },
    {
      kind: "tool",
      server: "context-engine",
      title: 'get_context(target="shop/cart.py:total_price")',
      detail: "3 bucăți de cod alese, 286 din 8000 de tokeni.",
      showContext: true,
    },
    {
      kind: "tool",
      server: "sandbox",
      title: "run_tests()",
      detail: "1 test picat: test_total_with_discount. Așteptat 90.0, primit -900.0.",
      status: "fail",
    },
    {
      kind: "agent",
      title: "Am găsit cauza",
      detail: "discount vine în procente (10), dar codul îl folosește ca fracție (0.10).",
    },
    {
      kind: "edit",
      title: "Am pregătit modificarea 1 în sandbox",
      detail: "shop/cart.py, 1 linie schimbată.",
      showChange: 1,
    },
    {
      kind: "tool",
      server: "sandbox",
      title: "run_tests()",
      detail: "12 teste trecute, 0 picate.",
      status: "ok",
    },
    {
      kind: "done",
      title: "Gata",
      detail: "Reducerea se calculează acum în procente. Apasă „Rulează QA” ca să verifici modificările.",
    },
  ],

  // Pașii agentului QA, când apeși „Rulează QA” (ADR-0002: QA pornit de utilizator).
  qa: [
    {
      kind: "tool",
      server: "sandbox",
      title: "QA · run_tests()",
      detail: "12 teste trecute, 0 picate.",
      status: "ok",
    },
    {
      kind: "tool",
      server: "sandbox",
      title: "QA · run_command()",
      detail: "Am încercat o reducere de 150%: totalul iese -50.0. Ar trebui să dea eroare.",
      status: "fail",
    },
    {
      kind: "agent",
      title: "QA · am propus 2 modificări",
      detail: "O verificare a reducerii și un test nou. Apar pe rând în coloana din mijloc.",
      addsChanges: [2, 3],
    },
    {
      kind: "done",
      title: "QA · rezumat gata",
      detail: "Acum verifici modificările una câte una.",
      showSummary: true,
    },
  ],

  // Rezumatul scris de QA la final.
  summary: {
    good: [
      "Bug-ul e reparat: o reducere de 10% dă acum 90.0.",
      "Toate cele 12 teste trec.",
    ],
    bad: [
      "O reducere de peste 100% dă un total negativ (150% → -50.0).",
    ],
    improve: [
      "Verificarea reducerii, să fie între 0 și 100 (modificarea 2).",
      "Un test nou pentru cazul ăsta (modificarea 3).",
    ],
  },

  // Modificările propuse. Stau în sandbox până le aprobi.
  // În diff, type: "same" (neschimbat), "del" (șters, roșu), "add" (adăugat, verde)
  changes: [
    {
      id: 1,
      author: "Coder",
      title: "Repară calculul reducerii",
      path: "shop/cart.py",
      lines: [
        { type: "same", oldNo: 8, newNo: 8, text: "        total += item.price * item.quantity" },
        { type: "same", oldNo: 9, newNo: 9, text: "    if discount:" },
        { type: "del", oldNo: 10, newNo: null, text: "        total = total * (1 - discount)" },
        { type: "add", oldNo: null, newNo: 10, text: "        total = total * (1 - discount / 100)" },
        { type: "same", oldNo: 11, newNo: 11, text: "    return round_price(total)" },
      ],
    },
    {
      id: 2,
      author: "QA",
      title: "Nu accepta reduceri sub 0% sau peste 100%",
      path: "shop/cart.py",
      lines: [
        { type: "same", oldNo: 4, newNo: 4, text: "def total_price(items, discount=0):" },
        { type: "same", oldNo: 5, newNo: 5, text: '    """Totalul coșului, cu reducere în procente."""' },
        { type: "add", oldNo: null, newNo: 6, text: "    if not 0 <= discount <= 100:" },
        { type: "add", oldNo: null, newNo: 7, text: '        raise ValueError("discount între 0 și 100")' },
        { type: "same", oldNo: 6, newNo: 8, text: "    total = 0" },
      ],
    },
    {
      id: 3,
      author: "QA",
      title: "Adaugă un test pentru reducere de peste 100%",
      path: "tests/test_cart.py",
      lines: [
        { type: "same", oldNo: 16, newNo: 16, text: "    assert total_price(items, discount=10) == 90.0" },
        { type: "add", oldNo: null, newNo: 17, text: "" },
        { type: "add", oldNo: null, newNo: 18, text: "" },
        { type: "add", oldNo: null, newNo: 19, text: "def test_discount_peste_100():" },
        { type: "add", oldNo: null, newNo: 20, text: "    with pytest.raises(ValueError):" },
        { type: "add", oldNo: null, newNo: 21, text: "        total_price([Item(10.0, 1)], discount=150)" },
      ],
    },
  ],

  // Ce cod a ales motorul de context (câmpurile din D4: path, linii, conținut, scor, motiv).
  context: {
    budget: 8000,
    used: 286,
    truncated: false,
    items: [
      {
        path: "shop/cart.py",
        start_line: 4,
        end_line: 11,
        score: 1.0,
        reason: "Simbolul cerut (target): total_price",
        content: [
          "def total_price(items, discount=0):",
          '    """Totalul coșului, cu reducere în procente."""',
          "    total = 0",
          "    for item in items:",
          "        total += item.price * item.quantity",
          "    if discount:",
          "        total = total * (1 - discount)",
          "    return round_price(total)",
        ].join("\n"),
      },
      {
        path: "shop/pricing.py",
        start_line: 1,
        end_line: 3,
        score: 0.65,
        reason: "Importat de shop/cart.py (round_price)",
        content: [
          "def round_price(value):",
          '    """Rotunjește la 2 zecimale."""',
          "    return round(value, 2)",
        ].join("\n"),
      },
      {
        path: "tests/test_cart.py",
        start_line: 14,
        end_line: 16,
        score: 0.4,
        reason: "Potrivire text: total_price",
        content: [
          "def test_total_with_discount():",
          "    items = [Item(price=50.0, quantity=2)]",
          "    assert total_price(items, discount=10) == 90.0",
        ].join("\n"),
      },
    ],
  },
};
