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

{{/* remove metadata keys */}}
{{- define "airbyte-module.remove-metadata-keys" -}}
{{- $_ := unset . "expected_format" }}
{{- $_ := unset . "emit_format" }}
{{- end -}}

/*
return the map which contains the additional properties for a connector.
The input to this function is a list of candidate connectors that have the
same connection name (i.e., "mysql") and connection operation type (i.e., "write"). */}}
{{- define "airbyte-module.get-connector" -}}
{{- $connectionFormat := .connectionFormat }}
{{ range $item := .additionalProperties }}
   {{ if or (not (hasKey $item "expected_format")) (eq $connectionFormat (get $item "expected_format")) }}
     {{- mustToJson $item }}
   {{- end -}}
{{- end -}}
{{- end -}}
