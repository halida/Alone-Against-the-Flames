const { computed, createApp, nextTick, onMounted, ref, watch } = Vue;

const SAVE_KEY = 'alone-against-the-flames-save-v1';

createApp({
  setup() {
    const book = ref(window.BOOK_DATA || null);
    const currentKey = ref('intro');
    const history = ref([]);
    const visited = ref(new Set(['intro']));
    const jumpInput = ref('');
    const diceResult = ref('');
    const loading = ref(false);
    const error = ref('');

    const currentNode = computed(() => {
      if (!book.value) return null;
      if (currentKey.value === 'intro') return book.value.intro;
      return book.value.sections[String(currentKey.value)] || null;
    });

    const displayParagraphs = computed(() => currentNode.value?.body?.length
      ? currentNode.value.body
      : currentNode.value?.text?.split('\n\n') || []);

    const canGoBack = computed(() => history.value.length > 0);
    const visitedCount = computed(() => [...visited.value].filter((item) => item !== 'intro').length);

    function restoreSave() {
      try {
        const raw = localStorage.getItem(SAVE_KEY);
        if (!raw) return;
        const save = JSON.parse(raw);
        if (save.currentKey) currentKey.value = save.currentKey;
        if (Array.isArray(save.history)) history.value = save.history;
        if (Array.isArray(save.visited)) visited.value = new Set(save.visited);
      } catch {
        localStorage.removeItem(SAVE_KEY);
      }
    }

    function saveGame() {
      localStorage.setItem(SAVE_KEY, JSON.stringify({
        currentKey: currentKey.value,
        history: history.value,
        visited: [...visited.value],
      }));
    }

    function scrollToTop() {
      nextTick(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    }

    function setCurrent(key, remember = true) {
      const normalizedKey = key === 'intro' ? 'intro' : Number(key);
      if (normalizedKey !== 'intro' && !book.value?.sections[String(normalizedKey)]) {
        diceResult.value = `没有找到段落 ${key}`;
        return;
      }

      if (remember) history.value.push(currentKey.value);
      currentKey.value = normalizedKey;
      visited.value = new Set([...visited.value, normalizedKey]);
      saveGame();
      scrollToTop();
    }

    function choose(target) {
      setCurrent(target);
    }

    function goBack() {
      if (!history.value.length) return;
      const previous = history.value.pop();
      currentKey.value = previous;
      saveGame();
      scrollToTop();
    }

    function restart() {
      history.value = [];
      visited.value = new Set(['intro']);
      currentKey.value = 'intro';
      diceResult.value = '';
      saveGame();
      scrollToTop();
    }

    function clearSave() {
      localStorage.removeItem(SAVE_KEY);
      restart();
    }

    function jumpToInput() {
      const target = Number(jumpInput.value);
      if (!Number.isInteger(target) || target < 1 || target > 270) {
        diceResult.value = '请输入 1 到 270 之间的段落编号。';
        return;
      }
      jumpInput.value = '';
      setCurrent(target);
    }

    function roll(sides) {
      const value = Math.floor(Math.random() * sides) + 1;
      diceResult.value = `D${sides}: ${value}`;
    }

    onMounted(() => {
      if (!book.value) {
        error.value = '没有找到嵌入的游戏数据，请确认 book-data.js 与 index.html 在同一目录。';
        return;
      }
      restoreSave();
    });

    watch(currentKey, () => {
      document.title = currentKey.value === 'intro'
        ? '向火独行 | Alone Against the Flames'
        : `段落 ${currentKey.value} | 向火独行`;
    });

    return {
      book,
      currentKey,
      currentNode,
      displayParagraphs,
      history,
      visitedCount,
      jumpInput,
      diceResult,
      loading,
      error,
      canGoBack,
      choose,
      goBack,
      restart,
      clearSave,
      jumpToInput,
      roll,
    };
  },
}).mount('#app');
