import 'package:flutter/material.dart';

import '../core/utils/formatters.dart';
import '../models/selected_video.dart';

class SelectedVideoCard extends StatelessWidget {
  const SelectedVideoCard({
    required this.video,
    required this.onClear,
    required this.onReplace,
    super.key,
  });

  final SelectedVideo video;
  final VoidCallback? onClear;
  final VoidCallback? onReplace;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final showRotation = video.rotation != null && video.rotation != 0;

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.55),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 46,
                  height: 46,
                  decoration: BoxDecoration(
                    color: theme.colorScheme.primaryContainer,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(
                    Icons.play_arrow_rounded,
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        video.displayName,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        video.mimeType ?? video.extension,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _InfoChip(
                  icon: Icons.storage_rounded,
                  label: formatBytes(video.sizeBytes),
                ),
                _InfoChip(
                  icon: Icons.schedule_rounded,
                  label: formatDuration(video.duration),
                ),
                _InfoChip(
                  icon: Icons.aspect_ratio_rounded,
                  label: video.friendlyResolution,
                ),
                if (showRotation)
                  _InfoChip(
                    icon: Icons.screen_rotation_alt_rounded,
                    label: '${video.rotation} graus',
                  ),
              ],
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                OutlinedButton.icon(
                  onPressed: onReplace,
                  icon: const Icon(Icons.swap_horiz),
                  label: const Text('Trocar video'),
                ),
                TextButton.icon(
                  onPressed: onClear,
                  icon: const Icon(Icons.close),
                  label: const Text('Remover'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  const _InfoChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(
          alpha: 0.62,
        ),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 6),
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
