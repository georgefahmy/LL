import React, { useState, useEffect, useRef } from 'react';
import { 
  TrendingUp, Calendar, Edit3, Settings, Play, Shield, 
  HelpCircle, User, Award, List, CheckCircle2, XCircle, Search, RefreshCw
} from 'lucide-react';
import llLogo from './assets/ll_app_logo.png';

import { 
  dbInstance, 
  loadAllQuestions, 
  saveUserAnswer, 
  updateUserAnswer, 
  getQuestionAnswersHistory, 
  type Question, 
  type UserAnswer 
} from './data/db';

declare global {
  interface Window {
    electronAPI: {
      loginToLL: (username: string, password: string) => Promise<{ success: boolean; profileId?: string; username?: string; error?: string }>;
      fetchLL: (url: string) => Promise<{ success: boolean; data?: string; error?: string }>;
      openLoginWindow: () => Promise<{ success: boolean; profileId?: string; username?: string; error?: string }>;
      runLuckAnalysis: (args: { season: number; matchday: number; usernames: string[]; rundle: boolean }) => Promise<{ success: boolean; data?: any[]; error?: string }>;
      debugAllQuestions: (season: number) => Promise<{ success: boolean; path?: string; error?: string }>;
    };
  }
}

const CATEGORIES = [
  "ALL",
  "AMER HIST",
  "ART",
  "BUS/ECON",
  "CLASS MUSIC",
  "CURR EVENTS",
  "FILM",
  "FOOD/DRINK",
  "GAMES/SPORT",
  "GEOGRAPHY",
  "LANGUAGE",
  "LIFESTYLE",
  "LITERATURE",
  "MATH",
  "POP MUSIC",
  "SCIENCE",
  "TELEVISION",
  "THEATRE",
  "WORLD HIST"
];

const App: React.FC = () => {
const directLoginToLL = async (username: string, password: string): Promise<{ success: boolean; profileId?: string; username?: string; error?: string }> => {
  return window.electronAPI.loginToLL(username, password);
};

const directFetchLL = async (url: string): Promise<{ success: boolean; data?: string; error?: string }> => {
  return window.electronAPI.fetchLL(url);
};


  // Defense Tactics States
  const [opponentsList, setOpponentsList] = useState<Record<string, { profileId: string; matchDay: number }>>({});
  const [selectedOpponent, setSelectedOpponent] = useState<string>("");

  // Defense page questions and radar state
  const [defenseQuestions, setDefenseQuestions] = useState<{ num: number; category: string; text: string }[]>([]);
  const [showRadarModal, setShowRadarModal] = useState<boolean>(false);
  const [defenseCategories, setDefenseCategories] = useState<string[]>(new Array(6).fill("ALL"));
  const [defenseSuggestions, setDefenseSuggestions] = useState<number[]>([]);
  const [defensePercentages, setDefensePercentages] = useState<string[]>([]);
  const [hunScore, setHunScore] = useState<string>("");
  const [defenseLoading, setDefenseLoading] = useState<boolean>(false);
  const [userCategoryStats, setUserCategoryStats] = useState<Record<string, number>>({});
  const [oppCategoryStats, setOppCategoryStats] = useState<Record<string, number>>({});

  // Luck Analysis States
  const [luckSeason, setLuckSeason] = useState<string>("");
  const [luckMatchday, setLuckMatchday] = useState<string>("25");
  const [luckUsernames, setLuckUsernames] = useState<string>("");
  const [luckRundleOnly, setLuckRundleOnly] = useState<boolean>(false);
  const [luckResults, setLuckResults] = useState<any[]>([]);
  const [luckLoading, setLuckLoading] = useState<boolean>(false);
  const [luckSortKey, setLuckSortKey] = useState<string>("LuckPctile");
  const [luckSortAsc, setLuckSortAsc] = useState<boolean>(false);
  // Navigation State
  const [currentPage, setCurrentPage] = useState<'practice' | 'mockday' | 'onedays' | 'minileagues' | 'settings' | 'defense' | 'luck'>('practice');
  const [isLoading, setIsLoading] = useState(true);
  
  const [downloadStatus, setDownloadStatus] = useState<string>("");
  const [syncSeason, setSyncSeason] = useState<string>("109");
  // Database state
  const [allQuestions, setAllQuestions] = useState<Question[]>([]);
  const [filteredQuestions, setFilteredQuestions] = useState<Question[]>([]);
  
  // Practice Filter States
  const [selectedSeason, setSelectedSeason] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [minPercent, setMinPercent] = useState<number>(0);
  const [maxPercent, setMaxPercent] = useState<number>(100);
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  // Current question states
  const isInitialMount = useRef(true);
  const [currentIdx, setCurrentIdx] = useState<number>(0);
  const [userSubmission, setUserSubmission] = useState<string>('');
  const [showAnswer, setShowAnswer] = useState<boolean>(false);
  const [lastSavedAnswer, setLastSavedAnswer] = useState<UserAnswer | null>(null);
  const [submitFeedback, setSubmitFeedback] = useState<{ submitted: boolean; correct: boolean } | null>(null);

  // Mock Match Day States
  const [mockThreshold, setMockThreshold] = useState<number>(0);
  const [mockSeed, setMockSeed] = useState<string>('');
  const [mockQuestions, setMockQuestions] = useState<Question[]>([]);
  const [mockSubmissions, setMockSubmissions] = useState<string[]>(['', '', '', '', '', '']);
  const [mockRevealed, setMockRevealed] = useState<boolean[]>([false, false, false, false, false, false]);
  const [mockFeedback, setMockFeedback] = useState<{ submitted: boolean; correct: boolean }[]>([
    { submitted: false, correct: false },
    { submitted: false, correct: false },
    { submitted: false, correct: false },
    { submitted: false, correct: false },
    { submitted: false, correct: false },
    { submitted: false, correct: false }
  ]);

  // One Day Specials States
  const [oneDaysList, setOneDaysList] = useState<{ title: string; url: string; date: string }[]>([]);
  const [oneDaysLoading, setOneDaysLoading] = useState<boolean>(false);
  const [selectedOneDay, setSelectedOneDay] = useState<any>(null);
  const [oneDaySearchQuery, setOneDaySearchQuery] = useState<string>('');
  const [oneDayAnswers, setOneDayAnswers] = useState<string[]>([]);
  const [oneDayRevealed, setOneDayRevealed] = useState<boolean[]>([]);

  // Mini Leagues States
  const [miniLeaguesList, setMiniLeaguesList] = useState<{ title: string; url: string; date: string; number_of_players: string }[]>([]);
  const [miniLeaguesLoading, setMiniLeaguesLoading] = useState<boolean>(false);
  const [selectedMiniLeague, setSelectedMiniLeague] = useState<any>(null);
  const [miniAnswers, setMiniAnswers] = useState<Record<string, string>>({}); // maps question key to submission
  const [miniRevealed, setMiniRevealed] = useState<Record<string, boolean>>({}); // maps question key to show/hide

  // Settings / Account States
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [profileId, setProfileId] = useState<string>('');
  const [loginStatus, setLoginStatus] = useState<string>('');
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);

  // Load database on mount
  useEffect(() => {
    // Clear user answers from previous sessions
    dbInstance.user_answers.clear().catch(err => {
      console.error("Failed to clear previous user answers session data", err);
    });

    loadAllQuestions()
      .then((qs) => {
        setAllQuestions(qs);
        setFilteredQuestions(qs);
        setIsLoading(false);
        
        // Pick a random question to start
        if (qs.length > 0) {
          const rand = Math.floor(Math.random() * qs.length);
          setCurrentIdx(rand);
        }
      })
      .catch((err) => {
        console.error("Database initialization failed", err);
        setIsLoading(false);
      });

    // Check settings for login credentials
    dbInstance.settings.toArray().then((settings) => {
      const u = settings.find(s => s.key === 'username')?.value || '';
      const p = settings.find(s => s.key === 'password')?.value || '';
      const pid = settings.find(s => s.key === 'profileId')?.value || '';
      
      if (p) setPassword(p);
      if (pid) {
        setProfileId(pid);
        setIsLoggedIn(true);
        
        // A valid LL username is a short alphanumeric string — never contains {, }, >, <
        const usernameIsValid = u && u.length < 30 && !/[{}<>]/.test(u) && u !== 'LearnedLeaguer';

        if (usernameIsValid) {
          setUsername(u);
        } else {
          // Corrupt or placeholder username — re-fetch the real one from profile page
          window.electronAPI.fetchLL(`https://www.learnedleague.com/profiles.php?${pid}`).then(res => {
            if (res.success && res.data) {
              const m1 = res.data.match(/<[^>]+class="namecss"[^>]*>\s*([^<]+)\s*</);
              const m2 = res.data.match(/<h1[^>]*>\s*([^<]+)\s*<\/h1>/);
              const m3 = res.data.match(/<title>([^-<]+)\s*-\s*LearnedLeague<\/title>/);
              const matched = m1 || m2 || m3;
              if (matched) {
                const correctUsername = matched[1].trim();
                if (correctUsername && !/[{}<>]/.test(correctUsername) && correctUsername !== 'LearnedLeaguer') {
                  setUsername(correctUsername);
                  dbInstance.settings.put({ key: 'username', value: correctUsername });
                }
              }
            }
          });
        }
      }
    });
  }, []);

  // Update filtered questions list whenever filter state changes
  useEffect(() => {
    if (allQuestions.length === 0) return;

    let filtered = allQuestions;

    if (selectedSeason !== 'ALL') {
      filtered = filtered.filter(q => q.season === parseInt(selectedSeason));
    }
    if (selectedCategory !== 'ALL') {
      filtered = filtered.filter(q => q.category.toUpperCase() === selectedCategory.toUpperCase());
    }
    
    // Difficulty filters
    filtered = filtered.filter(q => {
      const pct = parseFloat(q.percent);
      if (isNaN(pct)) return true;
      return pct >= minPercent && pct <= maxPercent;
    });

    // Search query filter
    if (searchQuery.trim() !== '') {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(q => 
        q.question.toLowerCase().includes(query) || 
        q.answer.toLowerCase().includes(query) ||
        q.category.toLowerCase().includes(query)
      );
    }

    setFilteredQuestions(filtered);
    if (isInitialMount.current) {
      if (filtered.length > 0) {
        const rand = Math.floor(Math.random() * filtered.length);
        setCurrentIdx(rand);
      }
      isInitialMount.current = false;
    } else {
      setCurrentIdx(0);
    }
  }, [selectedSeason, selectedCategory, minPercent, maxPercent, searchQuery, allQuestions]);

  // Load history when current question changes
  useEffect(() => {
    if (filteredQuestions.length === 0 || currentIdx >= filteredQuestions.length) {
      setSubmitFeedback(null);
      setLastSavedAnswer(null);
      return;
    }
    const currentQ = filteredQuestions[currentIdx];
    getQuestionAnswersHistory(currentQ.id).then((history) => {
      if (history.length > 0) {
        const last = history[history.length - 1];
        setLastSavedAnswer(last);
        setSubmitFeedback({
          submitted: true,
          correct: last.correct === 1
        });
        setUserSubmission(last.submitted_answer);
        setShowAnswer(true);
      } else {
        setLastSavedAnswer(null);
        setSubmitFeedback(null);
        setUserSubmission('');
        setShowAnswer(false);
      }
    });
  }, [currentIdx, filteredQuestions]);

  // Automatically calculate defense suggestions & HUN when opponent or tab changes
  useEffect(() => {
    if (currentPage === 'defense' && selectedOpponent && opponentsList[selectedOpponent]) {
      handleCalculateDefense(selectedOpponent, opponentsList);
      loadDefenseQuestions(selectedOpponent, opponentsList);
    }
  }, [selectedOpponent, currentPage, opponentsList]);

  // Keep luck analysis usernames synchronized with logged-in username
  useEffect(() => {
    if (username) {
      setLuckUsernames(username);
    }
  }, [username]);

  // Fetch OneDays list
  const handleLoadOneDays = async () => {
    setOneDaysLoading(true);
    try {
      const res = await directFetchLL("https://www.learnedleague.com/oneday/onedaysalpha.php");
      if (res.success && res.data) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(res.data, 'text/html');
        const rows = doc.querySelectorAll('table.std.min tbody tr');
        const parsedList: any[] = [];
        
        rows.forEach((row, index) => {
          if (index === 0) return; // Header
          const tdTitle = row.querySelector('td.std-left');
          const tdDate = row.querySelector('td.std-midleft');
          if (tdTitle && tdDate) {
            const title = tdTitle.textContent?.trim() || "";
            const link = tdTitle.querySelector('a')?.getAttribute('href') || "";
            const date = tdDate.textContent?.trim() || "";
            if (title && link) {
              parsedList.push({
                title,
                url: "https://www.learnedleague.com" + link,
                date
              });
            }
          }
        });
        
        setOneDaysList(parsedList);
      } else {
        alert("Failed to load OneDays: Access Forbidden (403). Make sure you are logged in under Settings.");
      }
    } catch (e) {
      console.error(e);
      alert("Error loading OneDays: " + e);
    }
    setOneDaysLoading(false);
  };

  // Load specific OneDay details
  const handleSelectOneDay = async (onedayItem: any) => {
    setOneDaysLoading(true);
    try {
      const pageRes = await directFetchLL(onedayItem.url);
      if (pageRes.success && pageRes.data) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(pageRes.data, 'text/html');
        
        // Parse tabs for metrics links
        let metricsUrl = "";
        const profileTab = doc.querySelector('ul#profilestabs a');
        if (profileTab) {
          metricsUrl = "https://www.learnedleague.com" + profileTab.getAttribute('href');
        }
        
        // Parse blurb description
        const blurbEl = doc.querySelector('div.blurb');
        const blurb = blurbEl ? blurbEl.textContent?.trim() : "No description available.";

        // Parse questions & answers
        const questionParas = doc.querySelectorAll('div#qs_close.qdivshow_wide p');
        const answerDivs = doc.querySelectorAll('div#qs_close.qdivshow_wide div.answer3');
        
        const qTexts: string[] = [];
        questionParas.forEach(p => {
          // Strip out leading numbers
          const cleanText = p.textContent?.replace(/^\d+\.\s*/, '').trim() || "";
          if (cleanText) qTexts.push(cleanText);
        });

        const ansTexts: string[] = [];
        answerDivs.forEach(div => {
          const cleanAns = div.textContent?.split('\n').pop()?.trim() || "";
          ansTexts.push(cleanAns);
        });

        // Load metrics if available
        let difficulty = "N/A";
        let overallAvg = "N/A";
        let playerNum = "N/A";
        if (metricsUrl) {
          const metricsRes = await directFetchLL(metricsUrl);
          if (metricsRes.success && metricsRes.data) {
            const mDoc = parser.parseFromString(metricsRes.data, 'text/html');
            // Extract difficulty/metrics
            const statCells = mDoc.querySelectorAll('table.std tbody tr td');
            if (statCells.length > 5) {
              overallAvg = statCells[0].textContent?.trim() || "N/A";
              difficulty = statCells[1].textContent?.trim() || "N/A";
              playerNum = statCells[4].textContent?.trim() || "N/A";
            }
          }
        }

        const dataQuestions = qTexts.map((q, idx) => ({
          question: q,
          answer: ansTexts[idx] || ""
        }));

        setSelectedOneDay({
          title: onedayItem.title,
          date: onedayItem.date,
          blurb,
          difficulty_rating: difficulty,
          overall_average: overallAvg,
          number_of_players: playerNum,
          questions: dataQuestions
        });

        setOneDayAnswers(new Array(dataQuestions.length).fill(''));
        setOneDayRevealed(new Array(dataQuestions.length).fill(false));
      }
    } catch (e) {
      alert("Error loading OneDay details: " + e);
    }
    setOneDaysLoading(false);
  };

  // Fetch MiniLeagues List
  const handleLoadMiniLeagues = async () => {
    setMiniLeaguesLoading(true);
    try {
      const res = await directFetchLL("https://www.learnedleague.com/mini/");
      if (res.success && res.data) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(res.data, 'text/html');
        const rows = doc.querySelectorAll('table.std.min tbody tr');
        const parsedList: any[] = [];
        
        rows.forEach((row, idx) => {
          if (idx < 3) return; // Headers and spacing
          const tdTitle = row.querySelector('td.std-left');
          const tdDate = row.querySelector('td.std-midleft');
          const tdPlayers = row.querySelector('td.std-mid');
          if (tdTitle && tdDate) {
            const title = tdTitle.textContent?.trim() || "";
            const link = tdTitle.querySelector('a')?.getAttribute('href') || "";
            const date = tdDate.textContent?.trim() || "";
            const players = tdPlayers ? tdPlayers.textContent?.trim() : "N/A";
            if (title && link) {
              parsedList.push({
                title,
                url: "https://www.learnedleague.com" + link,
                date,
                number_of_players: players
              });
            }
          }
        });
        setMiniLeaguesList(parsedList);
      } else {
        alert("Failed to load Mini Leagues: Access Forbidden (403). Make sure you are logged in under Settings.");
      }
    } catch (e) {
      alert("Error loading Mini Leagues: " + e);
    }
    setMiniLeaguesLoading(false);
  };

  // Load specific MiniLeague details
  const handleSelectMiniLeague = async (miniItem: any) => {
    setMiniLeaguesLoading(true);
    try {
      const res = await directFetchLL(miniItem.url);
      if (res.success && res.data) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(res.data, 'text/html');
        
        // Find match days list
        const matchRows = doc.querySelectorAll('table.mtch tr');
        const matches: { title: string; url: string }[] = [];
        
        matchRows.forEach(row => {
          const a = row.querySelector('a');
          if (a) {
            matches.push({
              title: row.textContent?.trim() || "",
              url: "https://www.learnedleague.com" + a.getAttribute('href')
            });
          }
        });

        // Scraping each match page questions (up to 12 match days, 6 questions each)
        const matchDaysData: Record<string, { q: string; a: string; key: string }[]> = {};
        
        // Loop through matches and load questions synchronously (or in parallel)
        // To be fast and friendly, load first 3 match days to verify, or all
        for (let idx = 0; idx < Math.min(matches.length, 12); idx++) {
          const match = matches[idx];
          const mRes = await directFetchLL(match.url);
          if (mRes.success && mRes.data) {
            const mDoc = parser.parseFromString(mRes.data, 'text/html');
            const qEls = mDoc.querySelectorAll('div.ind-Q20');
            const aEls = mDoc.querySelectorAll('div.a-red');
            
            const list: any[] = [];
            for (let j = 0; j < qEls.length; j++) {
              const qText = qEls[j].textContent?.trim() || "";
              const aText = aEls[j] ? aEls[j].textContent?.trim() : "";
              list.push({
                q: qText,
                a: aText,
                key: `D${idx+1}Q${j+1}`
              });
            }
            matchDaysData[`Day ${idx+1}`] = list;
          }
        }

        setSelectedMiniLeague({
          title: miniItem.title,
          date: miniItem.date,
          number_of_players: miniItem.number_of_players,
          matchDays: matchDaysData
        });
        
        setMiniAnswers({});
        setMiniRevealed({});
      }
    } catch (e) {
      alert("Error loading MiniLeague details: " + e);
    }
    setMiniLeaguesLoading(false);
  };

  // Submit Answer to Practice Question
  const handleSubmitPractice = () => {
    if (filteredQuestions.length === 0) return;
    const currentQ = filteredQuestions[currentIdx];
    
    // Normalize and compare
    const isCorrect = userSubmission.toLowerCase().trim() === currentQ.answer.toLowerCase().trim();
    
    const ansObj: UserAnswer = {
      question_id: currentQ.id,
      submitted_answer: userSubmission,
      date: new Date().toISOString(),
      correct: isCorrect ? 1 : 0,
      override: 0
    };
    
    saveUserAnswer(ansObj).then((id) => {
      setLastSavedAnswer({ ...ansObj, id });
      setSubmitFeedback({
        submitted: true,
        correct: isCorrect
      });
      setShowAnswer(true);
    });
  };

  // Toggle Override
  const handleToggleOverride = () => {
    if (!lastSavedAnswer || !lastSavedAnswer.id) return;
    const newCorrect = !submitFeedback?.correct;
    
    updateUserAnswer(lastSavedAnswer.id, newCorrect).then(() => {
      setSubmitFeedback({
        submitted: true,
        correct: newCorrect
      });
    });
  };


  // Defense: Load Opponents from logged-in user profile page
  const handleLoadOpponents = async () => {
    if (!profileId) {
      alert("Please log in first under Settings.");
      return;
    }
    setDefenseLoading(true);
    try {
      const res = await window.electronAPI.fetchLL(`https://www.learnedleague.com/profiles.php?${profileId}&1`);
      if (res.success && res.data) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(res.data, "text/html");
        const table = doc.querySelector('table[summary="Data table for LL results"]');
        const parsedOpponents: Record<string, { profileId: string; matchDay: number }> = {};
        if (table) {
          const rows = table.querySelectorAll("tr");
          rows.forEach((row, idx) => {
            if (idx === 0) return;
            const cells = row.querySelectorAll("td");
            if (cells.length > 2) {
              const mdText = cells[0]?.textContent?.trim() || "";
              const match = mdText.match(/\d+/);
              const matchDay = match ? parseInt(match[0]) : NaN;
              const img = row.querySelector("img");
              const a = row.querySelector("a.flag");
              if (img && a) {
                const title = img.getAttribute("title") || "";
                const href = a.getAttribute("href") || "";
                const pid = href.split("?")[1] || "";
                if (title && pid && !isNaN(matchDay)) {
                  parsedOpponents[title] = { profileId: pid, matchDay };
                }
              }
            }
          });
        }
        setOpponentsList(parsedOpponents);
        if (Object.keys(parsedOpponents).length > 0) {
          setSelectedOpponent(Object.keys(parsedOpponents)[0]);
        }
      }
    } catch (e) {
      alert("Error loading opponents: " + e);
    }
    setDefenseLoading(false);
  };

  // Defense: Calculate HUN and point suggestions
  const handleCalculateDefense = async (oppName = selectedOpponent, list = opponentsList) => {
    if (!oppName || !list[oppName]) {
      return;
    }
    setDefenseLoading(true);
    const oppId = typeof list[oppName] === 'object' ? (list[oppName] as any).profileId : list[oppName];
    try {
      // 1. Fetch Opponent and User profile pages to parse category correctness
      const oppRes = await window.electronAPI.fetchLL(`https://www.learnedleague.com/profiles.php?${oppId}&1`);
      const userRes = await window.electronAPI.fetchLL(`https://www.learnedleague.com/profiles.php?${profileId}&1`);
      
      if (oppRes.success && oppRes.data && userRes.success && userRes.data) {
        const parser = new DOMParser();
        
        // Parse Opponent
        const oDoc = parser.parseFromString(oppRes.data, "text/html");
        const oRows = oDoc.querySelectorAll("table.std.sortable.this_sea.std_bord tbody tr");
        const oppCategoryPercents: Record<string, number> = {};
        oRows.forEach(row => {
          const cells = row.querySelectorAll("td");
          if (cells.length > 1) {
            const catName = cells[0].textContent?.trim() || "";
            const parts = cells[1].textContent?.split("-") || [];
            const correct = parseInt(parts[0]) || 0;
            const total = parseInt(parts[1]) || 0;
            oppCategoryPercents[catName] = total > 0 ? (correct / total) : 0;
          }
        });
        setOppCategoryStats(oppCategoryPercents);

        // Parse User
        const uDoc = parser.parseFromString(userRes.data, "text/html");
        const uRows = uDoc.querySelectorAll("table.std.sortable.this_sea.std_bord tbody tr");
        const userCategoryPercents: Record<string, number> = {};
        uRows.forEach(row => {
          const cells = row.querySelectorAll("td");
          if (cells.length > 1) {
            const catName = cells[0].textContent?.trim() || "";
            const parts = cells[1].textContent?.split("-") || [];
            const correct = parseInt(parts[0]) || 0;
            const total = parseInt(parts[1]) || 0;
            userCategoryPercents[catName] = total > 0 ? (correct / total) : 0;
          }
        });
        setUserCategoryStats(userCategoryPercents);

        // Compute defense suggestion: [3, 2, 2, 1, 1, 0] allocated from lowest opponent percent to highest
        const activeCategories = [...defenseCategories];
        const indexedCats = activeCategories.map((cat, idx) => ({
          idx,
          cat,
          pct: oppCategoryPercents[cat] !== undefined ? oppCategoryPercents[cat] : 0
        }));

        // Sort ascending by percent
        const sortedCats = [...indexedCats].sort((a, b) => a.pct - b.pct);
        const rawScores = [3, 2, 2, 1, 1, 0];
        
        const suggestions = new Array(6).fill(0);
        sortedCats.forEach((item, sortedIdx) => {
          suggestions[item.idx] = rawScores[sortedIdx];
        });

        setDefenseSuggestions(suggestions);
        setDefensePercentages(activeCategories.map(cat => {
          const val = oppCategoryPercents[cat];
          return val !== undefined ? `${(val * 100).toFixed(2)}%` : "0.00%";
        }));

        // 2. Fetch User and Opponent question histories to calculate HUN similarity
        setHunScore("Calculating...");
        const userQRes = await window.electronAPI.fetchLL(`https://www.learnedleague.com/profiles.php?${profileId}&9`);
        const oppQRes = await window.electronAPI.fetchLL(`https://www.learnedleague.com/profiles.php?${oppId}&9`);

        if (userQRes.success && userQRes.data && oppQRes.success && oppQRes.data) {
          const uDoc = parser.parseFromString(userQRes.data, "text/html");
          const oDoc = parser.parseFromString(oppQRes.data, "text/html");

          const parseHistory = (qhDoc: Document) => {
            const history: Record<string, boolean> = {};
            const qhistory = qhDoc.querySelector("div.qhistory");
            if (qhistory) {
              const liList = qhistory.querySelectorAll("li");
              liList.forEach(li => {
                const qhRows = li.querySelectorAll("table.qh tr");
                qhRows.forEach((r, rIdx) => {
                  if (rIdx === 0) return;
                  const cells = r.querySelectorAll("td");
                  if (cells.length > 2) {
                    const a = cells[0].querySelectorAll("a")[2];
                    const qId = a ? a.getAttribute("href")?.split("?")[1] : "";
                    const correct = cells[2].querySelector("svg")?.getAttribute("aria-label")?.includes("Check") || false;
                    if (qId) {
                      history[qId] = correct;
                    }
                  }
                });
              });
            }
            return history;
          };

          const userHistory = parseHistory(uDoc);
          const oppHistory = parseHistory(oDoc);

          let raw = 0;
          let total = 0;
          Object.keys(userHistory).forEach(key => {
            if (oppHistory[key] !== undefined) {
              total++;
              if (userHistory[key] === oppHistory[key]) {
                raw++;
              }
            }
          });

          const hun = total > 0 ? (raw / total) : 0;
          setHunScore(`${(hun * 100).toFixed(2)}% (Matches compared: ${total})`);
        } else {
          setHunScore("Failed (mismatched profiles history)");
        }
      }
    } catch (e) {
      alert("Error calculating defense: " + e);
      setHunScore("Error");
    }
    setDefenseLoading(false);
  };

  // Defense: Load Match Day's questions directly in the background
  const loadDefenseQuestions = async (oppName: string, list: Record<string, { profileId: string; matchDay: number }>) => {
    const oppInfo = list[oppName];
    if (!oppInfo) return;
    
    const day = typeof oppInfo === 'object' ? oppInfo.matchDay : null;
    if (!day) return;
    
    setDefenseQuestions([]);
    
    try {
      const season = parseInt(syncSeason) || 109;
      const dayStr = day.toString().padStart(2, '0');
      
      // 1. Try database first
      const dbQs = await dbInstance.questions
        .where('season').equals(season)
        .toArray();
      
      const filtered = dbQs.filter(q => q.question_num.startsWith(`D${dayStr}`));
      
      if (filtered.length > 0) {
        filtered.sort((a, b) => a.id.localeCompare(b.id));
        setDefenseQuestions(filtered.map((q, idx) => ({
          num: idx + 1,
          category: q.category,
          text: q.question
        })));
        return;
      }
      
      // 2. Fallback: Fetch directly from match.php on-demand
      const res = await window.electronAPI.fetchLL(`https://www.learnedleague.com/match.php?${season}&${day}`);
      if (res.success && res.data) {
        const parser = new DOMParser();
        const mDoc = parser.parseFromString(res.data, "text/html");
        const qDivs = mDoc.querySelectorAll("div.ind-Q20");
        if (qDivs.length > 0) {
          const parsed = Array.from(qDivs).map((qDiv, idx) => {
            const clone = qDiv.cloneNode(true) as HTMLElement;
            const labelSpan = clone.querySelector("span.ind-Numb3");
            if (labelSpan) labelSpan.remove();
            
            const fullText = clone.textContent?.trim() || "";
            
            let category = "ALL";
            let text = fullText;
            const catMatch = fullText.match(/^([A-Z][A-Z /]+?)\s*-\s+(.+)/s);
            if (catMatch) {
              category = catMatch[1].trim();
              text = catMatch[2].trim();
            }
            
            return {
              num: idx + 1,
              category,
              text
            };
          });
          setDefenseQuestions(parsed);
        }
      }
    } catch (err) {
      console.error("Error loading defense questions", err);
    }
  };

  // Luck: Trigger Python luck analysis script
  const handleCalculateLuck = async () => {
    setLuckLoading(true);
    try {
      // Find latest season if none provided
      let targetSeason = luckSeason.trim();
      if (!targetSeason) {
        const res = await window.electronAPI.fetchLL("https://www.learnedleague.com/allrundles.php");
        if (res.success && res.data) {
          const parser = new DOMParser();
          const doc = parser.parseFromString(res.data, "text/html");
          targetSeason = doc.querySelector("h1")?.textContent?.split(":")[0].replace("LL", "").trim() || "";
        }
      }

      if (!targetSeason) {
        alert("Could not fetch current season. Please enter season manually.");
        setLuckLoading(false);
        return;
      }

      const usernamesList = luckUsernames.split(",").map(u => u.trim());
      const runRes = await window.electronAPI.runLuckAnalysis({
        season: parseInt(targetSeason),
        matchday: parseInt(luckMatchday),
        usernames: usernamesList,
        rundle: luckRundleOnly
      });

      if (runRes.success && runRes.data) {
        setLuckResults(runRes.data);
      } else {
        alert("Luck calculation failed: " + runRes.error);
      }
    } catch (e) {
      alert("Error calculating luck: " + e);
    }
    setLuckLoading(false);
  };

  // Sync latest questions (diff only)
  const handleDownloadLatestData = async () => {
    if (!profileId) {
      alert("Please log in first.");
      return;
    }
    const season = parseInt(syncSeason.trim());
    if (isNaN(season)) {
      alert("Please enter a valid season number.");
      return;
    }
    
    setDownloadStatus(`Syncing Season ${season}... Checking database for diff.`);
    try {
      const parser = new DOMParser();
      let newQuestionsCount = 0;
      
      // Loop through all 25 matchdays
      for (let day = 1; day <= 25; day++) {
        const dayStr = day.toString().padStart(2, "0");
        const firstQId = `S${season}D${dayStr}Q1`;
        
        // If first question of this matchday exists, skip the day (diff sync)
        const exists = await dbInstance.questions.get(firstQId);
        if (exists) {
          continue;
        }
        
        setDownloadStatus(`Downloading Day ${day} of Season ${season}...`);
        
        // Fetch the matchday page — contains both questions and answers
        const matchRes = await window.electronAPI.fetchLL(
          `https://www.learnedleague.com/match.php?${season}&${day}`
        );
        if (!matchRes.success || !matchRes.data) {
          console.log(`[Sync] Day ${day} fetch failed:`, matchRes.error);
          break;
        }
        
        const mDoc = parser.parseFromString(matchRes.data, "text/html");
        
        // Stop if matchday not yet active
        const bodyText = mDoc.body.textContent || "";
        if (bodyText.includes("not yet active") || bodyText.includes("No Active Match Day")) {
          break;
        }
        
        // Questions are in div.ind-Q20 — text after the "Qx." span prefix
        // Answers are in div[id$='ANS'] with class a-red (display:none but readable by DOMParser)
        const qDivs = mDoc.querySelectorAll("div.ind-Q20");
        const ansDivs = mDoc.querySelectorAll("div[id$='ANS'].a-red");
        
        if (qDivs.length === 0) {
          console.log(`[Sync] Day ${day}: no questions found (ind-Q20), skipping.`);
          continue;
        }
        
        // Parse date from lh-pagetype div (e.g. "May 18, 2026: LL109 Match Day 1 Results")
        const pageTypeEl = mDoc.querySelector(".lh-pagetype");
        let dateStr = "";
        if (pageTypeEl) {
          const dtMatch = pageTypeEl.textContent?.match(/^([^:]+):/);
          if (dtMatch) dateStr = dtMatch[1].trim();
        }
        
        // Parse Leaguewide % correct from the metrics table (last "Leaguewide" row, Q1-Q6 columns)
        const leaguewideRow = Array.from(mDoc.querySelectorAll("tr")).find(
          tr => tr.textContent?.trim().startsWith("Leaguewide")
        );
        const leaguewidePercents: string[] = [];
        if (leaguewideRow) {
          const cells = leaguewideRow.querySelectorAll("td");
          // cells[0]=label, cells[1]=Forf%, cells[2]=Q1...cells[7]=Q6
          for (let i = 2; i <= 7; i++) {
            leaguewidePercents.push(cells[i]?.textContent?.trim() || "50");
          }
        }
        
        const dayQuestions: Question[] = [];
        
        for (let qIdx = 0; qIdx < qDivs.length; qIdx++) {
          const qNum = qIdx + 1;
          const qDiv = qDivs[qIdx];
          
          // Remove the Qx. label span to get clean question text
          const labelSpan = qDiv.querySelector("span.ind-Numb3");
          if (labelSpan) labelSpan.remove();
          const fullText = qDiv.textContent?.trim() || "";
          
          // Category is the ALL-CAPS prefix before " - "
          let foundCategory = "ALL";
          let qText = fullText;
          const catMatch = fullText.match(/^([A-Z][A-Z /]+?)\s*-\s+(.+)/s);
          if (catMatch) {
            const catCandidate = catMatch[1].trim();
            for (const cat of CATEGORIES) {
              if (cat !== "ALL" && catCandidate.toUpperCase().includes(cat)) {
                foundCategory = cat;
                break;
              }
            }
            qText = catMatch[2].trim();
          }
          
          // Answer is in div[id='Q{qNum}1ANS'] or div[id='Q{qNum}ANS'] with class a-red
          const ansDiv = ansDivs[qIdx];
          const ansText = ansDiv?.textContent?.trim() || "";
          
          if (!qText || !ansText) {
            console.log(`[Sync] D${day}Q${qNum}: missing q="${!!qText}" or ans="${!!ansText}", skipping.`);
            continue;
          }
          
          const foundPercent = leaguewidePercents[qIdx] || "50";
          const qId = `S${season}D${dayStr}Q${qNum}`;
          
          dayQuestions.push({
            id: qId,
            question: qText,
            answer: ansText,
            season: season,
            date: dateStr || `S${season} Day ${day}`,
            category: foundCategory,
            percent: foundPercent,
            question_num: `D${dayStr}Q${qNum}`,
            defense: `${qNum}.0`,
            url: `https://www.learnedleague.com/question.php?${season}&${day}&${qNum}`,
            clickable_link: "",
            A: foundPercent,
            B: foundPercent,
            C: foundPercent,
            D: foundPercent,
            E: foundPercent,
            R: foundPercent
          });
        }
        
        if (dayQuestions.length > 0) {
          await dbInstance.questions.bulkPut(dayQuestions);
          newQuestionsCount += dayQuestions.length;
          setDownloadStatus(`Day ${day}: saved ${dayQuestions.length} questions (${newQuestionsCount} total)`);
        }
      }
      
      setDownloadStatus(`Sync complete! Saved ${newQuestionsCount} new questions.`);
      // Reload questions in UI
      const updatedQs = await dbInstance.questions.toArray();
      setAllQuestions(updatedQs);
      setFilteredQuestions(updatedQs);
    } catch (e: any) {
      setDownloadStatus(`Sync failed: ${e.message}`);
    }
  };

  // Open login popup window
  const handleOpenLoginPopup = async () => {
    setLoginStatus("Opening login window...");
    try {
      const res = await window.electronAPI.openLoginWindow();
      if (res.success && res.profileId && res.username) {
        setProfileId(res.profileId);
        setUsername(res.username);
        setIsLoggedIn(true);
        setLoginStatus("Login Successful!");
        
        // Save to Dexie settings
        await dbInstance.settings.put({ key: 'username', value: res.username });
        await dbInstance.settings.put({ key: 'profileId', value: res.profileId });
      } else {
        setLoginStatus(res.error || "Authentication cancelled or failed.");
      }
    } catch (err: any) {
      setLoginStatus("Popup Error: " + err.message);
    }
  };

  // Logout
  const handleLogout = async () => {
    setIsLoggedIn(false);
    setProfileId('');
    setUsername('');
    setPassword('');
    setLoginStatus("Logged Out.");
    
    await dbInstance.settings.delete('username');
    await dbInstance.settings.delete('password');
    await dbInstance.settings.delete('profileId');
  };

  // Mock Day Generation
  const handleGenerateMockDay = () => {
    // filter questions based on threshold
    let eligible = allQuestions.filter(q => {
      const pct = parseFloat(q.percent);
      return !isNaN(pct) && pct >= mockThreshold;
    });

    if (eligible.length < 6) {
      alert("Not enough questions matching the difficulty threshold! Try decreasing the threshold.");
      return;
    }

    // shuffle
    let shuffled = [...eligible];
    shuffled.sort(() => Math.random() - 0.5);

    // Pick 6
    const selected = shuffled.slice(0, 6);
    setMockQuestions(selected);
    setMockSubmissions(['', '', '', '', '', '']);
    setMockRevealed([false, false, false, false, false, false]);
    setMockFeedback(new Array(6).fill({ submitted: false, correct: false }));
  };

  // Submit Answer to a mock question
  const handleSubmitMockAnswer = (idx: number) => {
    const q = mockQuestions[idx];
    const sub = mockSubmissions[idx];
    const isCorrect = sub.toLowerCase().trim() === q.answer.toLowerCase().trim();
    
    const newFeedback = [...mockFeedback];
    newFeedback[idx] = { submitted: true, correct: isCorrect };
    setMockFeedback(newFeedback);

    const newRevealed = [...mockRevealed];
    newRevealed[idx] = true;
    setMockRevealed(newRevealed);
  };

  const getMockScore = () => {
    return mockFeedback.reduce((acc, curr) => acc + (curr.submitted && curr.correct ? 1 : 0), 0);
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo-container">
          <img src={llLogo} alt="LearnedLeague Logo" className="logo-icon" style={{ width: '32px', height: '32px', objectFit: 'contain' }} />
          <span className="logo-text">LearnedLeague</span>
        </div>
        
        <ul className="nav-list">
          <li 
            className={`nav-item ${currentPage === 'practice' ? 'active' : ''}`}
            onClick={() => setCurrentPage('practice')}
          >
            <HelpCircle size={20} />
            <span>Practice Qs</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'mockday' ? 'active' : ''}`}
            onClick={() => setCurrentPage('mockday')}
          >
            <Play size={20} />
            <span>Mock Match Day</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'onedays' ? 'active' : ''}`}
            onClick={() => setCurrentPage('onedays')}
          >
            <Calendar size={20} />
            <span>OneDay Specials</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'minileagues' ? 'active' : ''}`}
            onClick={() => setCurrentPage('minileagues')}
          >
            <List size={20} />
            <span>Mini Leagues</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'defense' ? 'active' : ''}`}
            onClick={() => { setCurrentPage('defense'); handleLoadOpponents(); }}
          >
            <Shield size={20} />
            <span>Defense Tactics</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'luck' ? 'active' : ''}`}
            onClick={() => setCurrentPage('luck')}
          >
            <TrendingUp size={20} />
            <span>Luck Analysis</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'settings' ? 'active' : ''}`}
            onClick={() => setCurrentPage('settings')}
          >
            <Settings size={20} />
            <span>Settings / Login</span>
          </li>
        </ul>

        <div className="sidebar-footer">
          <p className="sidebar-footer-text">
            {isLoggedIn ? `Logged in as ${username}` : "Offline / Not Logged In"}
          </p>
        </div>
      </aside>

      {/* Main Panel Content */}
      <main className="main-content">
        {isLoading ? (
          <div className="spinner-container">
            <div className="spinner"></div>
            <p>Initializing LearnedLeague Database...</p>
          </div>
        ) : (
          <>
            {/* 1. Practice Panel */}
            {currentPage === 'practice' && (
              <div className="practice-container">
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Question Practice</h1>
                    <p>Practice with past LearnedLeague seasons</p>
                  </div>
                </header>

                {/* Filters */}
                <div className="glass-panel form-row">
                  <div className="form-group">
                    <label>Season</label>
                    <select 
                      className="select-input"
                      value={selectedSeason}
                      onChange={(e) => setSelectedSeason(e.target.value)}
                    >
                      <option value="ALL">All Seasons</option>
                      {/* Generates seasons 60 to latest in DB */}
                      {Array.from(new Set(allQuestions.map(q => q.season)))
                        .sort((a,b) => b-a)
                        .map(s => (
                          <option key={s} value={s}>Season {s}</option>
                        ))
                      }
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Category</label>
                    <select 
                      className="select-input"
                      value={selectedCategory}
                      onChange={(e) => setSelectedCategory(e.target.value)}
                    >
                      {CATEGORIES.map(c => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Min % Correct</label>
                    <input 
                      type="number" 
                      className="text-input"
                      value={minPercent} 
                      onChange={(e) => setMinPercent(parseInt(e.target.value) || 0)}
                      min="0" max="100" 
                    />
                  </div>

                  <div className="form-group">
                    <label>Max % Correct</label>
                    <input 
                      type="number" 
                      className="text-input"
                      value={maxPercent} 
                      onChange={(e) => setMaxPercent(parseInt(e.target.value) || 100)}
                      min="0" max="100" 
                    />
                  </div>

                  <div className="form-group" style={{ minWidth: '250px' }}>
                    <label>Search text</label>
                    <div style={{ position: 'relative' }}>
                      <input 
                        type="text" 
                        className="text-input" 
                        placeholder="Search Q/A..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                      />
                    </div>
                  </div>
                </div>

                {filteredQuestions.length === 0 ? (
                  <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem' }}>
                    <p style={{ color: 'var(--text-muted)' }}>No questions match your current search parameters.</p>
                  </div>
                ) : (
                  <>
                    {/* Active Question Box */}
                    <div className="glass-panel question-panel">
                      <div className="question-meta-grid" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', flex: 1 }}>
                          <div className="question-meta-item" style={{ padding: '0.4rem 0.6rem', flex: '1', minWidth: '110px' }}>
                            <span className="question-meta-label" style={{ fontSize: '0.65rem' }}>Season / Day</span>
                            <span className="question-meta-value" style={{ fontSize: '0.85rem' }}>S{filteredQuestions[currentIdx].season} Day {filteredQuestions[currentIdx].question_num.substring(1,3)}</span>
                          </div>
                          <div className="question-meta-item" style={{ padding: '0.4rem 0.6rem', flex: '1', minWidth: '110px' }}>
                            <span className="question-meta-label" style={{ fontSize: '0.65rem' }}>Category</span>
                            <span className="question-meta-value" style={{ fontSize: '0.85rem' }}>{filteredQuestions[currentIdx].category}</span>
                          </div>
                          <div className="question-meta-item" style={{ padding: '0.4rem 0.6rem', flex: '1', minWidth: '110px' }}>
                            <span className="question-meta-label" style={{ fontSize: '0.65rem' }}>LL Difficulty</span>
                            <span className="question-meta-value" style={{ fontSize: '0.85rem' }}>{filteredQuestions[currentIdx].percent}% Correct</span>
                          </div>
                          <div className="question-meta-item" style={{ padding: '0.4rem 0.6rem', flex: '1', minWidth: '110px' }}>
                            <span className="question-meta-label" style={{ fontSize: '0.65rem' }}>Defense Value</span>
                            <span className="question-meta-value" style={{ fontSize: '0.85rem' }}>{filteredQuestions[currentIdx].defense}</span>
                          </div>
                        </div>

                        {/* Navigation Buttons Row */}
                        <div style={{ display: 'flex', gap: '0.35rem' }}>
                          <button 
                            className="btn" 
                            style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
                            disabled={currentIdx === 0}
                            onClick={() => setCurrentIdx(prev => prev - 1)}
                          >
                            Previous
                          </button>
                          <button 
                            className="btn" 
                            style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
                            onClick={() => setCurrentPage('practice')}
                          >
                            Reset
                          </button>
                          <button 
                            className="btn" 
                            style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
                            disabled={currentIdx === filteredQuestions.length - 1}
                            onClick={() => setCurrentIdx(prev => prev + 1)}
                          >
                            Next
                          </button>
                        </div>
                      </div>

                      <div className="question-text-box">
                        {filteredQuestions[currentIdx].question}
                      </div>

                      {/* Rundle Stats */}
                      <div className="table-wrapper" style={{ margin: 0 }}>
                        <table className="budget-table">
                          <thead>
                            <tr>
                              <th>Rundle A</th>
                              <th>Rundle B</th>
                              <th>Rundle C</th>
                              <th>Rundle D</th>
                              <th>Rundle E</th>
                              <th>Rookie (R)</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td>{filteredQuestions[currentIdx].A}%</td>
                              <td>{filteredQuestions[currentIdx].B}%</td>
                              <td>{filteredQuestions[currentIdx].C}%</td>
                              <td>{filteredQuestions[currentIdx].D}%</td>
                              <td>{filteredQuestions[currentIdx].E}%</td>
                              <td>{filteredQuestions[currentIdx].R}%</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      {/* Answer Entry */}
                      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                        <input 
                          type="text" 
                          className="text-input" 
                          placeholder="Type your answer here..."
                          value={userSubmission}
                          onChange={(e) => {
                            setUserSubmission(e.target.value);
                          }}
                          onKeyDown={(e) => e.key === 'Enter' && handleSubmitPractice()}
                          disabled={showAnswer}
                        />
                        <button 
                          className="btn primary" 
                          onClick={handleSubmitPractice}
                          disabled={showAnswer || !userSubmission.trim()}
                        >
                          Submit
                        </button>
                      </div>

                      {/* Feedback Panel */}
                      {showAnswer && (
                        <div className={`answer-panel ${submitFeedback?.correct ? 'correct' : 'incorrect'}`}>
                          <div>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>CORRECT ANSWER:</p>
                            <h3 style={{ fontSize: '1.25rem', fontFamily: 'var(--font-title)' }}>{filteredQuestions[currentIdx].answer}</h3>
                            
                            {submitFeedback && (
                              <p style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                {submitFeedback.correct ? (
                                  <><CheckCircle2 size={16} color="var(--accent-emerald)" /> Correct</>
                                ) : (
                                  <><XCircle size={16} color="var(--accent-rose)" /> Incorrect (Your answer: "{userSubmission}")</>
                                )}
                              </p>
                            )}
                          </div>

                          {submitFeedback && (
                            <label className="override-checkbox-label">
                              <input 
                                type="checkbox" 
                                className="override-checkbox"
                                checked={submitFeedback.correct} 
                                onChange={handleToggleOverride}
                              />
                              Override assessment
                            </label>
                          )}
                        </div>
                      )}

                      {/* Navigation bar */}
                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button 
                            className="btn cyan"
                            onClick={() => setShowAnswer(prev => !prev)}
                          >
                            {showAnswer ? "Hide Answer" : "Reveal Answer"}
                          </button>
                          <button 
                            className="btn primary"
                            onClick={() => {
                              const rand = Math.floor(Math.random() * filteredQuestions.length);
                              setCurrentIdx(rand);
                            }}
                          >
                            <RefreshCw size={16} /> Random Question
                          </button>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* 2. Mock Match Day */}
            {currentPage === 'mockday' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Mock Match Day</h1>
                    <p>Play 6 random questions in a simulated match day</p>
                  </div>
                </header>

                <div className="glass-panel form-row">
                  <div className="form-group">
                    <label>Min Difficulty Threshold (% Correct)</label>
                    <input 
                      type="number" 
                      className="text-input" 
                      value={mockThreshold}
                      onChange={(e) => setMockThreshold(parseInt(e.target.value) || 0)}
                      min="0" max="95"
                    />
                  </div>

                  <div className="form-group">
                    <label>Seed (Optional)</label>
                    <input 
                      type="text" 
                      className="text-input" 
                      placeholder="Random seed..."
                      value={mockSeed}
                      onChange={(e) => setMockSeed(e.target.value)}
                    />
                  </div>

                  <button className="btn primary" onClick={handleGenerateMockDay}>
                    Generate Match Day
                  </button>
                </div>

                {mockQuestions.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '2rem' }}>
                    <div className="glass-panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ fontSize: '1.5rem' }}>Match Progress</h3>
                      <span style={{ fontSize: '1.25rem', color: 'var(--accent-cyan)', fontWeight: 'bold' }}>
                        Score: {getMockScore()} / 6
                      </span>
                    </div>

                    {mockQuestions.map((q, idx) => (
                      <div className="glass-panel" key={q.id}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 'bold' }}>QUESTION {idx + 1} ({q.category}) - {q.percent}% Correct</span>
                        </div>
                        <p style={{ fontSize: '1.15rem', marginBottom: '1rem' }}>{q.question}</p>
                        
                        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
                          <input 
                            type="text" 
                            className="text-input" 
                            placeholder="Type answer..."
                            value={mockSubmissions[idx]}
                            onChange={(e) => {
                              const list = [...mockSubmissions];
                              list[idx] = e.target.value;
                              setMockSubmissions(list);
                            }}
                            disabled={mockFeedback[idx].submitted}
                          />
                          <button 
                            className="btn primary"
                            disabled={mockFeedback[idx].submitted || !mockSubmissions[idx].trim()}
                            onClick={() => handleSubmitMockAnswer(idx)}
                          >
                            Submit
                          </button>
                        </div>

                        {mockRevealed[idx] && (
                          <div className={`answer-panel ${mockFeedback[idx].correct ? 'correct' : 'incorrect'}`} style={{ margin: 0 }}>
                            <div>
                              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>CORRECT ANSWER:</p>
                              <h3>{q.answer}</h3>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 3. One Day Specials */}
            {currentPage === 'onedays' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>One Day Specials</h1>
                    <p>Load and practice specialized single-topic quizzes</p>
                  </div>
                </header>

                <div className="glass-panel form-row">
                  <button className="btn primary" onClick={handleLoadOneDays}>
                    Retrieve OneDays List
                  </button>
                  
                  {oneDaysList.length > 0 && (
                    <div className="form-group" style={{ minWidth: '300px' }}>
                      <input 
                        type="text" 
                        className="text-input" 
                        placeholder="Search quiz titles..."
                        value={oneDaySearchQuery}
                        onChange={(e) => setOneDaySearchQuery(e.target.value)}
                      />
                    </div>
                  )}
                </div>

                {oneDaysLoading ? (
                  <div className="spinner-container">
                    <div className="spinner"></div>
                    <p>Fetching One Day Specials Data...</p>
                  </div>
                ) : (
                  <div className="stats-grid" style={{ marginTop: '1.5rem' }}>
                    {/* Left: list of quizzes */}
                    {oneDaysList.length > 0 && (
                      <div className="glass-panel scroll-panel">
                        <h3 style={{ marginBottom: '1rem' }}>Available Quizzes</h3>
                        <div className="data-table-wrapper">
                          <table className="data-table">
                            <thead>
                              <tr>
                                <th>Date</th>
                                <th>Topic</th>
                              </tr>
                            </thead>
                            <tbody>
                              {oneDaysList
                                .filter(item => item.title.toLowerCase().includes(oneDaySearchQuery.toLowerCase()))
                                .map((item) => (
                                  <tr 
                                    key={item.url} 
                                    style={{ cursor: 'pointer' }}
                                    onClick={() => handleSelectOneDay(item)}
                                  >
                                    <td style={{ fontSize: '0.85rem' }}>{item.date}</td>
                                    <td style={{ fontWeight: '500' }}>{item.title}</td>
                                  </tr>
                                ))
                              }
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Right: details of selected quiz */}
                    {selectedOneDay ? (
                      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        <div>
                          <h2 style={{ fontSize: '1.75rem', color: 'var(--accent-cyan)' }}>{selectedOneDay.title}</h2>
                          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loaded date: {selectedOneDay.date}</p>
                        </div>

                        <div className="question-meta-grid">
                          <div className="question-meta-item">
                            <span className="question-meta-label">Difficulty</span>
                            <span className="question-meta-value">{selectedOneDay.difficulty_rating}</span>
                          </div>
                          <div className="question-meta-item">
                            <span className="question-meta-label">Avg Score</span>
                            <span className="question-meta-value">{selectedOneDay.overall_average}%</span>
                          </div>
                          <div className="question-meta-item">
                            <span className="question-meta-label">Players</span>
                            <span className="question-meta-value">{selectedOneDay.number_of_players}</span>
                          </div>
                        </div>

                        <div className="question-text-box" style={{ fontSize: '0.95rem', padding: '1rem' }}>
                          <p style={{ fontWeight: 'bold', marginBottom: '0.25rem', color: 'var(--accent-cyan)' }}>Description blurb:</p>
                          {selectedOneDay.blurb}
                        </div>

                        <div className="scroll-panel" style={{ maxHeight: '400px' }}>
                          {selectedOneDay.questions.map((q: any, idx: number) => (
                            <div key={idx} style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--card-border)', paddingBottom: '1rem' }}>
                              <p style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>Q{idx + 1}: {q.question}</p>
                              
                              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                <input 
                                  type="text" 
                                  className="text-input" 
                                  placeholder="Answer..."
                                  value={oneDayAnswers[idx]}
                                  onChange={(e) => {
                                    const list = [...oneDayAnswers];
                                    list[idx] = e.target.value;
                                    setOneDayAnswers(list);
                                  }}
                                  disabled={oneDayRevealed[idx]}
                                />
                                <button 
                                  className="btn primary"
                                  onClick={() => {
                                    const list = [...oneDayRevealed];
                                    list[idx] = true;
                                    setOneDayRevealed(list);
                                  }}
                                >
                                  Submit
                                </button>
                              </div>

                              {oneDayRevealed[idx] && (
                                <div className="answer-panel correct" style={{ margin: 0, padding: '0.5rem 1rem' }}>
                                  <p>Correct: <span style={{ fontWeight: 'bold' }}>{q.answer}</span></p>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      oneDaysList.length > 0 && (
                        <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <p style={{ color: 'var(--text-muted)' }}>Select a One Day Special from the table to load its questions.</p>
                        </div>
                      )
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 4. Mini Leagues */}
            {currentPage === 'minileagues' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Mini Leagues</h1>
                    <p>Load and practice past Mini-Leagues</p>
                  </div>
                </header>

                <div className="glass-panel form-row">
                  <button className="btn primary" onClick={handleLoadMiniLeagues}>
                    Retrieve MiniLeagues List
                  </button>
                </div>

                {miniLeaguesLoading ? (
                  <div className="spinner-container">
                    <div className="spinner"></div>
                    <p>Fetching Mini Leagues Data...</p>
                  </div>
                ) : (
                  <div className="stats-grid" style={{ marginTop: '1.5rem' }}>
                    {/* Left: list of MiniLeagues */}
                    {miniLeaguesList.length > 0 && (
                      <div className="glass-panel scroll-panel">
                        <h3 style={{ marginBottom: '1rem' }}>Available Mini Leagues</h3>
                        <div className="data-table-wrapper">
                          <table className="data-table">
                            <thead>
                              <tr>
                                <th>Date</th>
                                <th>Name</th>
                                <th>Players</th>
                              </tr>
                            </thead>
                            <tbody>
                              {miniLeaguesList.map((item) => (
                                <tr 
                                  key={item.url} 
                                  style={{ cursor: 'pointer' }}
                                  onClick={() => handleSelectMiniLeague(item)}
                                >
                                  <td style={{ fontSize: '0.85rem' }}>{item.date}</td>
                                  <td style={{ fontWeight: '500' }}>{item.title}</td>
                                  <td>{item.number_of_players}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Right: details of selected MiniLeague */}
                    {selectedMiniLeague ? (
                      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        <div>
                          <h2 style={{ fontSize: '1.75rem', color: 'var(--accent-cyan)' }}>{selectedMiniLeague.title}</h2>
                          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Date: {selectedMiniLeague.date} | Players: {selectedMiniLeague.number_of_players}</p>
                        </div>

                        <div className="scroll-panel" style={{ maxHeight: '500px' }}>
                          {Object.keys(selectedMiniLeague.matchDays).map((dayKey) => (
                            <div key={dayKey} style={{ marginBottom: '2rem' }}>
                              <h3 style={{ borderBottom: '1px solid var(--card-border)', paddingBottom: '0.5rem', marginBottom: '1rem', color: 'var(--accent-cyan)' }}>{dayKey}</h3>
                              
                              {selectedMiniLeague.matchDays[dayKey].map((q: any) => {
                                const qKey = `${dayKey}-${q.key}`;
                                return (
                                  <div key={q.key} style={{ marginBottom: '1.5rem', paddingLeft: '0.5rem' }}>
                                    <p style={{ fontWeight: '500', marginBottom: '0.5rem' }}>{q.key}: {q.q}</p>
                                    
                                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                      <input 
                                        type="text" 
                                        className="text-input" 
                                        placeholder="Answer..."
                                        value={miniAnswers[qKey] || ''}
                                        onChange={(e) => {
                                          setMiniAnswers(prev => ({
                                            ...prev,
                                            [qKey]: e.target.value
                                          }));
                                        }}
                                        disabled={miniRevealed[qKey]}
                                      />
                                      <button 
                                        className="btn primary"
                                        onClick={() => {
                                          setMiniRevealed(prev => ({
                                            ...prev,
                                            [qKey]: true
                                          }));
                                        }}
                                      >
                                        Submit
                                      </button>
                                    </div>

                                    {miniRevealed[qKey] && (
                                      <div className="answer-panel correct" style={{ margin: 0, padding: '0.5rem 1rem' }}>
                                        <p>Correct: <span style={{ fontWeight: 'bold' }}>{q.a}</span></p>
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      miniLeaguesList.length > 0 && (
                        <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <p style={{ color: 'var(--text-muted)' }}>Select a Mini League from the table to load its questions.</p>
                        </div>
                      )
                    )}
                  </div>
                )}
              </div>
            )}

            
            {/* Defense Tactics */}
            {currentPage === 'defense' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Defense Strategy</h1>
                    <p>Analyze opponent category stats and optimize defensive points allocation</p>
                  </div>
                </header>

                <div className="grid-container" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                  {/* Left Column: Strategy */}
                  <div className="glass-panel" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--card-border)", paddingBottom: "0.5rem" }}>
                      <h3 style={{ margin: 0 }}>Select Opponent</h3>
                      {hunScore && (
                        <span style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", fontWeight: "600", background: "rgba(0, 240, 255, 0.1)", padding: "0.25rem 0.6rem", borderRadius: "4px" }}>
                          HUN Similarity: {hunScore.includes(" (") ? hunScore.split(" (")[0] : hunScore}
                        </span>
                      )}
                    </div>
                    
                    <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                      <div className="form-group" style={{ flex: 1 }}>
                        <label>Opponent Player</label>
                        <select 
                          className="text-input" 
                          value={selectedOpponent}
                          onChange={(e) => setSelectedOpponent(e.target.value)}
                          style={{ background: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--card-border)" }}
                        >
                          {Object.keys(opponentsList).map(opp => (
                            <option key={opp} value={opp}>{opp}</option>
                          ))}
                        </select>
                      </div>
                      
                      <button 
                        className="btn secondary" 
                        onClick={handleLoadOpponents} 
                        style={{ marginTop: "1.3rem" }}
                        disabled={defenseLoading}
                      >
                        Refresh Opponents
                      </button>

                      <button 
                        className="btn secondary" 
                        onClick={() => setShowRadarModal(true)} 
                        style={{ marginTop: "1.3rem" }}
                        disabled={Object.keys(oppCategoryStats).length === 0}
                      >
                        View Radar Chart
                      </button>
                    </div>

                    <h3 style={{ borderBottom: "1px solid var(--card-border)", paddingBottom: "0.5rem", marginTop: "1rem" }}>Matchday Question Categories</h3>
                    
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {new Array(6).fill(0).map((_, idx) => (
                        <div key={idx} style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                          <span style={{ fontWeight: "600", width: "30px" }}>Q{idx + 1}:</span>
                          <select
                            className="text-input"
                            value={defenseCategories[idx]}
                            onChange={(e) => {
                              const updated = [...defenseCategories];
                              updated[idx] = e.target.value;
                              setDefenseCategories(updated);
                            }}
                            style={{ flex: 1, background: "var(--bg-secondary)", color: "var(--text-primary)" }}
                          >
                            <option value="ALL">Select Category...</option>
                            {CATEGORIES.map(cat => (
                              <option key={cat} value={cat}>{cat}</option>
                            ))}
                          </select>
                          
                          {defenseSuggestions[idx] !== undefined && (
                            <div style={{ display: "flex", gap: "0.5rem", width: "180px", justifyContent: "flex-end", fontSize: "0.9rem" }}>
                              <span style={{ color: "var(--text-muted)" }}>Sug: <strong style={{ color: "var(--accent-cyan)" }}>{defenseSuggestions[idx]} pts</strong></span>
                              <span style={{ color: "var(--text-muted)" }}>({defensePercentages[idx]})</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>

                    <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
                      <button className="btn primary" onClick={() => handleCalculateDefense()} disabled={defenseLoading}>
                        {defenseLoading ? "Calculating..." : "Calculate Strategy & HUN"}
                      </button>
                      <button 
                        className="btn secondary" 
                        onClick={() => {
                          setDefenseCategories(new Array(6).fill("ALL"));
                          setDefenseSuggestions([]);
                          setDefensePercentages([]);
                          setHunScore("");
                        }}
                      >
                        Clear
                      </button>
                    </div>
                  </div>

                  {/* Right Column: Questions List Display */}
                  <div className="glass-panel" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <h3 style={{ borderBottom: "1px solid var(--card-border)", paddingBottom: "0.5rem" }}>
                      Match Day {typeof opponentsList[selectedOpponent] === 'object' ? (opponentsList[selectedOpponent] as any).matchDay : ""} Questions
                    </h3>

                    {defenseLoading && (
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "4rem 0", color: "var(--text-secondary)", flex: 1, justifyContent: "center" }}>
                        <div className="spinner" style={{ marginBottom: "1rem" }}></div>
                        Loading questions...
                      </div>
                    )}

                    {!defenseLoading && defenseQuestions.length === 0 && (
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "4rem 0", color: "var(--text-muted)", flex: 1, textAlign: "center" }}>
                        No questions loaded. Select an opponent to view Match Day questions.
                      </div>
                    )}

                    {!defenseLoading && defenseQuestions.length > 0 && (
                      <div style={{ display: "flex", flexDirection: "column", gap: "1rem", overflowY: "auto", maxHeight: "580px", paddingRight: "0.5rem" }}>
                        {defenseQuestions.map((q) => (
                          <div key={q.num} style={{ padding: "1rem", background: "var(--bg-secondary)", borderRadius: "var(--border-radius-md)", border: "1px solid var(--card-border)" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem", fontSize: "0.85rem" }}>
                              <span style={{ fontWeight: "700", color: "var(--accent-cyan)" }}>Question {q.num}</span>
                            </div>
                            <p style={{ margin: 0, fontSize: "0.95rem", lineHeight: "1.5", color: "var(--text-primary)" }}>{q.text}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Modal Overlay for Radar Chart */}
                {showRadarModal && (
                  <div style={{
                    position: "fixed",
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: "rgba(0, 0, 0, 0.75)",
                    backdropFilter: "blur(4px)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    zIndex: 1000
                  }}>
                    <div className="glass-panel" style={{
                      width: "90%",
                      maxWidth: "520px",
                      padding: "2rem",
                      display: "flex",
                      flexDirection: "column",
                      gap: "1.5rem",
                      boxShadow: "0 20px 40px rgba(0, 0, 0, 0.5)",
                      border: "1px solid var(--card-border)",
                      animation: "fadeIn 0.2s ease-out"
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--card-border)", paddingBottom: "0.75rem" }}>
                        <h2 style={{ margin: 0, fontSize: "1.3rem", color: "var(--text-primary)" }}>
                          Category Comparison (Radar)
                        </h2>
                        <button 
                          className="btn secondary" 
                          onClick={() => setShowRadarModal(false)}
                          style={{ padding: "0.25rem 0.5rem", minWidth: "auto" }}
                        >
                          ✕
                        </button>
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                        {(() => {
                          const width = 440;
                          const height = 400;
                          const cx = width / 2;
                          const cy = height / 2;
                          const rMax = 120;
                          const categories = Object.keys(oppCategoryStats).filter(cat => cat && cat !== "Overall" && cat !== "TOTAL" && cat !== "AVG" && cat !== "ALL" && cat !== "Avg" && cat !== "Total");
                          const numAxes = categories.length || 6;

                          const getCoords = (i: number, val: number) => {
                            const angle = (i * 2 * Math.PI) / numAxes - Math.PI / 2;
                            const r = val * rMax;
                            return {
                              x: cx + r * Math.cos(angle),
                              y: cy + r * Math.sin(angle)
                            };
                          };

                          const getPolygonPath = (stats: Record<string, number>) => {
                            const points = categories.map((cat, i) => {
                              const pct = stats[cat] !== undefined ? stats[cat] : 0.5;
                              const { x, y } = getCoords(i, pct);
                              return `${x.toFixed(1)},${y.toFixed(1)}`;
                            });
                            return points.join(" ");
                          };

                          const userPoints = getPolygonPath(userCategoryStats);
                          const oppPoints = getPolygonPath(oppCategoryStats);
                          const gridLevels = [0.2, 0.4, 0.6, 0.8, 1.0];

                          return (
                            <div style={{ position: "relative", width: "100%", display: "flex", flexDirection: "column", alignItems: "center" }}>
                              <svg width={width} height={height} style={{ overflow: "visible" }}>
                                {gridLevels.map((lvl, idx) => {
                                  const points = Array.from({ length: numAxes }).map((_, i) => {
                                    const { x, y } = getCoords(i, lvl);
                                    return `${x},${y}`;
                                  }).join(" ");
                                  return (
                                    <polygon
                                      key={idx}
                                      points={points}
                                      fill="none"
                                      stroke="rgba(255, 255, 255, 0.08)"
                                      strokeWidth="1"
                                      strokeDasharray={lvl < 1.0 ? "3,3" : "none"}
                                    />
                                  );
                                })}

                                {categories.map((cat, i) => {
                                  const outer = getCoords(i, 1.0);
                                  const labelPos = getCoords(i, 1.25);
                                  return (
                                    <g key={i}>
                                      <line
                                        x1={cx}
                                        y1={cy}
                                        x2={outer.x}
                                        y2={outer.y}
                                        stroke="rgba(255, 255, 255, 0.08)"
                                        strokeWidth="1"
                                      />
                                      <text
                                        x={labelPos.x}
                                        y={labelPos.y + 3}
                                        fill="var(--text-secondary)"
                                        fontSize="8"
                                        fontWeight="600"
                                        textAnchor={
                                          Math.abs(labelPos.x - cx) < 15
                                            ? "middle"
                                            : labelPos.x > cx
                                            ? "start"
                                            : "end"
                                        }
                                      >
                                        {cat}
                                      </text>
                                    </g>
                                  );
                                })}

                                <polygon
                                  points={userPoints}
                                  fill="rgba(0, 240, 255, 0.12)"
                                  stroke="#00F0FF"
                                  strokeWidth="2"
                                />

                                <polygon
                                  points={oppPoints}
                                  fill="rgba(255, 0, 127, 0.12)"
                                  stroke="#FF007F"
                                  strokeWidth="2"
                                />

                                {categories.map((cat, i) => {
                                  const userVal = userCategoryStats[cat] !== undefined ? userCategoryStats[cat] : 0.5;
                                  const oppVal = oppCategoryStats[cat] !== undefined ? oppCategoryStats[cat] : 0.5;
                                  const userPt = getCoords(i, userVal);
                                  const oppPt = getCoords(i, oppVal);
                                  return (
                                    <g key={i}>
                                      <circle cx={userPt.x} cy={userPt.y} r="3.5" fill="#00F0FF" />
                                      <circle cx={oppPt.x} cy={oppPt.y} r="3.5" fill="#FF007F" />
                                    </g>
                                  );
                                })}
                              </svg>

                              <div style={{ display: "flex", gap: "1rem", justifyContent: "center", marginTop: "0.5rem", fontSize: "0.8rem" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                                  <span style={{ display: "inline-block", width: "12px", height: "12px", borderRadius: "2px", background: "#00F0FF" }}></span>
                                  <span style={{ color: "var(--text-secondary)" }}>You ({username})</span>
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                                  <span style={{ display: "inline-block", width: "12px", height: "12px", borderRadius: "2px", background: "#FF007F" }}></span>
                                  <span style={{ color: "var(--text-secondary)" }}>Opponent ({selectedOpponent})</span>
                                </div>
                              </div>
                            </div>
                          );
                        })()}
                      </div>

                      <div style={{ display: "flex", justifyContent: "flex-end", borderTop: "1px solid var(--card-border)", paddingTop: "0.75rem" }}>
                        <button className="btn secondary" onClick={() => setShowRadarModal(false)}>
                          Close
                        </button>
                      </div>
                    </div>
                  </div>
                )}

              </div>
            )}

            {/* Luck Analysis */}
            {currentPage === 'luck' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Luck Analysis</h1>
                    <p>Calculate luck adjustments by comparing actual points vs expected points using OLS regression models</p>
                  </div>
                </header>

                <div className="glass-panel" style={{ marginBottom: "1.5rem" }}>
                  <div style={{ display: "flex", gap: "1rem", alignItems: "flex-end", flexWrap: "wrap" }}>
                    <div className="form-group" style={{ width: "120px" }}>
                      <label>Season #</label>
                      <input 
                        type="text" 
                        className="text-input" 
                        placeholder="Latest"
                        value={luckSeason} 
                        onChange={(e) => setLuckSeason(e.target.value)} 
                      />
                    </div>

                    <div className="form-group" style={{ width: "120px" }}>
                      <label>Matchday #</label>
                      <input 
                        type="text" 
                        className="text-input" 
                        value={luckMatchday} 
                        onChange={(e) => setLuckMatchday(e.target.value)} 
                      />
                    </div>

                    <div className="form-group" style={{ flex: 1, minWidth: "200px" }}>
                      <label>Usernames (comma-separated)</label>
                      <input 
                        type="text" 
                        className="text-input" 
                        value={luckUsernames} 
                        onChange={(e) => setLuckUsernames(e.target.value)} 
                      />
                    </div>

                    <div style={{ display: "flex", alignItems: "center", height: "40px", paddingRight: "1rem" }}>
                      <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                        <input 
                          type="checkbox" 
                          checked={luckRundleOnly} 
                          onChange={(e) => setLuckRundleOnly(e.target.checked)} 
                        />
                        <span>Rundle-wide Analysis</span>
                      </label>
                    </div>

                    <button className="btn primary" onClick={handleCalculateLuck} disabled={luckLoading} style={{ height: "40px" }}>
                      {luckLoading ? "Running..." : "Run Luck Analysis"}
                    </button>
                  </div>
                </div>

                {luckResults.length > 0 && (() => {
                  const sortedResults = [...luckResults].sort((a, b) => {
                    let valA = a[luckSortKey];
                    let valB = b[luckSortKey];
                    
                    if (luckSortKey === "Record") {
                      valA = (parseInt(a.W) || 0) * 1000 + (parseInt(a.T) || 0);
                      valB = (parseInt(b.W) || 0) * 1000 + (parseInt(b.T) || 0);
                    }
                    
                    if (valA === undefined) valA = "";
                    if (valB === undefined) valB = "";
                    
                    if (typeof valA === "string") {
                      return luckSortAsc
                        ? valA.localeCompare(valB as string)
                        : (valB as string).localeCompare(valA);
                    } else {
                      return luckSortAsc
                        ? (valA as number) - (valB as number)
                        : (valB as number) - (valA as number);
                    }
                  });
                  
                  const handleSort = (key: string) => {
                    if (luckSortKey === key) {
                      setLuckSortAsc(!luckSortAsc);
                    } else {
                      setLuckSortKey(key);
                      const descFirst = ["LuckPctile", "Luck", "PTS", "Exp_PTS", "QPct", "TCA", "CAA", "Record"];
                      setLuckSortAsc(!descFirst.includes(key));
                    }
                  };
                  
                  const renderSortIndicator = (key: string) => {
                    if (luckSortKey !== key) return null;
                    return luckSortAsc ? " ▲" : " ▼";
                  };
                  
                  return (
                    <div className="glass-panel" style={{ overflowX: "auto" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                        <thead>
                          <tr style={{ borderBottom: "2px solid var(--card-border)", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("Player")}>Player{renderSortIndicator("Player")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("Rundle")}>Rundle{renderSortIndicator("Rundle")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("Record")}>Record{renderSortIndicator("Record")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("QPct")}>QPct{renderSortIndicator("QPct")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("TCA")}>TCA{renderSortIndicator("TCA")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("CAA")}>CAA{renderSortIndicator("CAA")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("PTS")}>PTS{renderSortIndicator("PTS")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("Exp_PTS")}>Expected PTS{renderSortIndicator("Exp_PTS")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("Luck")}>Luck Diff{renderSortIndicator("Luck")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("LuckPctile")}>Luck Pctile{renderSortIndicator("LuckPctile")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("Rank")}>Rank{renderSortIndicator("Rank")}</th>
                            <th style={{ padding: "0.75rem 1rem", cursor: "pointer", userSelect: "none" }} onClick={() => handleSort("Exp_Rank")}>Expected Rank{renderSortIndicator("Exp_Rank")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedResults.map((row, idx) => (
                            <tr 
                              key={idx} 
                              style={{ 
                                borderBottom: "1px solid var(--card-border)", 
                                fontSize: "0.9rem",
                                background: luckUsernames.split(",").map(u=>u.trim().toLowerCase()).includes(row.Player.toLowerCase()) ? "rgba(0, 240, 255, 0.08)" : "transparent"
                              }}
                            >
                              <td style={{ padding: "0.75rem 1rem", fontWeight: "bold" }}>{row.Player}</td>
                              <td style={{ padding: "0.75rem 1rem" }}>{row.Rundle}</td>
                              <td style={{ padding: "0.75rem 1rem" }}>{row.W}-{row.L}-{row.T}</td>
                              <td style={{ padding: "0.75rem 1rem" }}>{(row.QPct * 100).toFixed(1)}%</td>
                              <td style={{ padding: "0.75rem 1rem" }}>{row.TCA}</td>
                              <td style={{ padding: "0.75rem 1rem" }}>{row.CAA}</td>
                              <td style={{ padding: "0.75rem 1rem", fontWeight: "600" }}>{row.PTS}</td>
                              <td style={{ padding: "0.75rem 1rem" }}>{row.Exp_PTS}</td>
                              <td style={{ padding: "0.75rem 1rem", color: row.Luck >= 0 ? "#10B981" : "#EF4444", fontWeight: "bold" }}>
                                {row.Luck > 0 ? `+${row.Luck}` : row.Luck}
                              </td>
                              <td style={{ padding: "0.75rem 1rem", fontWeight: "bold", color: "var(--accent-cyan)" }}>{row.LuckPctile}%</td>
                              <td style={{ padding: "0.75rem 1rem" }}>{row.Rank}</td>
                              <td style={{ padding: "0.75rem 1rem" }}>{row.Exp_Rank}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );
                })()}
              </div>
            )}
            {/* 5. Settings / Login */}
            {currentPage === 'settings' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Settings & Accounts</h1>
                    <p>Configure LearnedLeague user authentication settings</p>
                  </div>
                </header>

                 <div className="glass-panel" style={{ maxWidth: '600px', margin: '0 auto' }}>
                  <h3 style={{ marginBottom: '1rem', borderBottom: '1px solid var(--card-border)', paddingBottom: '0.5rem' }}>LearnedLeague.com Authentication</h3>
                  
                  <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem', fontSize: '0.95rem', lineHeight: '1.6' }}>
                    LearnedLeague requires cookie authentication to fetch customized OneDay specials and MiniLeagues. 
                    Clicking the button below will launch a secure browser window to log in directly on the official LearnedLeague website, allowing you to solve any Cloudflare verification challenges.
                  </p>

                  <div style={{ display: 'flex', gap: '1rem' }}>
                    {isLoggedIn ? (
                      <button className="btn rose" onClick={handleLogout}>
                        Log Out
                      </button>
                    ) : (
                      <button className="btn primary" onClick={handleOpenLoginPopup}>
                        Sign In via LearnedLeague Website
                      </button>
                    )}
                  </div>

                  {loginStatus && (
                    <div 
                      style={{ 
                        marginTop: '1.5rem', 
                        padding: '1rem', 
                        borderRadius: 'var(--border-radius-md)', 
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--card-border)',
                        fontWeight: '500'
                      }}
                    >
                      {loginStatus}
                    </div>
                  )}


                  {isLoggedIn && (
                    <div style={{ marginTop: "1.5rem", padding: "1.25rem", borderRadius: "var(--border-radius-md)", background: "rgba(255, 255, 255, 0.03)", border: "1px solid var(--card-border)", display: "flex", flexDirection: "column", gap: "1rem" }}>
                      <h4 style={{ color: "var(--accent-cyan)", margin: 0 }}>Sync Database</h4>
                      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: 0, lineHeight: "1.5" }}>
                        Incremental Sync downloads newly published questions. Input the season number you wish to sync (e.g. 109). Already existing questions in IndexedDB will be skipped.
                      </p>
                      
                      <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                        <div className="form-group" style={{ width: "120px", marginBottom: 0 }}>
                          <input 
                            type="text" 
                            className="text-input" 
                            placeholder="Season #"
                            value={syncSeason}
                            onChange={(e) => setSyncSeason(e.target.value)}
                            style={{ padding: "0.4rem 0.6rem", fontSize: "0.9rem" }}
                          />
                        </div>
                        <button className="btn secondary" onClick={handleDownloadLatestData}>
                          Download Season Questions
                        </button>
                        {downloadStatus && (
                          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: "500" }}>
                            {downloadStatus}
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {isLoggedIn && (
                    <div style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', borderTop: '1px solid var(--card-border)', paddingTop: '1.25rem' }}>
                      <p>🟢 Logged in as: <strong style={{ color: 'var(--accent-cyan)' }}>{username}</strong></p>
                      <p>🪪 Profile ID: <strong style={{ color: 'var(--accent-cyan)' }}>{profileId}</strong></p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};

export default App;
