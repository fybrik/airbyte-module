{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "airbyte-module.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "airbyte-module.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "airbyte-module.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
returns true if the connection format is equal to the format in the
additional properties defined for a connector. If the additional properties does not
contain a format key then they are considered equal.
*/}}
{{- define "airbyte-module.is-format-equal" -}}
{{- if hasKey .additionalProperties "expected_format" -}}
{{- if eq (get .additionalProperties "expected_format") .connectionFormat -}}
{{- true }}
{{- end -}}
{{- else -}}
{{- true }}
{{- end -}}
{{- end -}}

{{/* remove metadata keys */}}
{{- define "airbyte-module.remove-metadata-keys" -}}
{{- $_ := unset . "expected_format" }}
{{- $_ := unset . "emit_format" }}
{{- $_ := unset . "emit_asset_key" }}
{{- end -}}
