// Shared shapes for config-step form state, lifted up to App.tsx so
// values survive when the user navigates back to an earlier step.

export interface Phase1FormValues {
  markers: string[];
  sampleCols: string[];
  normalization: string;
  sampling: string;
  sampleSize: number;
  drMethod: string;
  clusterMethods: string[];
  phenographK: number;
  flowsomRscript: string;
  depecheRscript: string;
  seed: number;
  outdir: string;
  forceRestart: boolean;
}

export function defaultPhase1FormValues(columns: string[], nonMarkerHint: string[]): Phase1FormValues {
  return {
    markers: columns.filter((c) => !nonMarkerHint.includes(c)),
    sampleCols: [],
    normalization: "z-score",
    sampling: "stratified-notproportional",
    sampleSize: 20000,
    drMethod: "none",
    clusterMethods: ["phenograph", "kmeans"],
    phenographK: 25,
    flowsomRscript: "",
    depecheRscript: "",
    seed: 42,
    outdir: "",
    forceRestart: true,
  };
}

export interface Phase2FormValues {
  phase1OutdirOverride: string; // blank = use the Phase 1 job from the previous step
  methods: string[];
  knnK: number;
  minVotes: number;
  templateMaxPerLabel: number;
  outdir: string;
}

export function defaultPhase2FormValues(annotatedMethods: string[]): Phase2FormValues {
  return {
    phase1OutdirOverride: "",
    methods: annotatedMethods,
    knnK: 25,
    minVotes: 2,
    templateMaxPerLabel: 500,
    outdir: "",
  };
}
