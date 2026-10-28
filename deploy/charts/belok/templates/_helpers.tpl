{{- define "belok.labels" -}}
app.kubernetes.io/part-of: belok
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{- define "belok.selector" -}}
app.kubernetes.io/part-of: belok
app.kubernetes.io/component: {{ . }}
{{- end }}

{{- define "belok.tag" -}}
{{- required "image.tag is required" .Values.image.tag -}}
{{- end }}

{{- define "belok.backendImage" -}}
{{ .Values.image.backend }}:{{ include "belok.tag" . }}
{{- end }}

{{- define "belok.podSecurity" -}}
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{- define "belok.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end }}

{{- define "belok.backendEnv" -}}
envFrom:
  - configMapRef:
      name: belok-config
  - secretRef:
      name: {{ .Values.secretName }}
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: {{ .Values.database.secretName }}
        key: {{ .Values.database.secretKey }}
{{- end }}
