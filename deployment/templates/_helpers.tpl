{{- define "pulsegrid.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "pulsegrid.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "pulsegrid.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "pulsegrid.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
app.kubernetes.io/name: {{ include "pulsegrid.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "pulsegrid.selectorLabels" -}}
app.kubernetes.io/name: {{ include "pulsegrid.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "pulsegrid.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "pulsegrid.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "pulsegrid.secretName" -}}
{{- default (printf "%s-secrets" (include "pulsegrid.fullname" .)) .Values.secrets.existingSecret -}}
{{- end -}}

{{- define "pulsegrid.webUrl" -}}
http://{{ include "pulsegrid.fullname" . }}-web:8000
{{- end -}}

{{/* Shared env wiring for every control-plane container. */}}
{{- define "pulsegrid.controlplaneEnvFrom" -}}
envFrom:
  - configMapRef:
      name: {{ include "pulsegrid.fullname" . }}-config
  - secretRef:
      name: {{ include "pulsegrid.secretName" . }}
{{- end -}}
